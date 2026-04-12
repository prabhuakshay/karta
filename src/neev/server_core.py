"""Core file and directory serving handlers for neev.

Handles serving individual files, directory listings, and ZIP downloads.
Each function follows the delegation pattern: the ``NeevHandler`` instance
is passed as the first argument.
"""

from __future__ import annotations

import logging
import os
import shutil
from typing import TYPE_CHECKING, BinaryIO

from neev.fs import (
    format_content_disposition,
    get_mime_type,
    is_previewable_type,
    list_directory,
)
from neev.html import render_directory_listing
from neev.server_utils import send_error
from neev.zip import ZipSizeLimitError, stream_zip


logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler
    from pathlib import Path

    from neev.config import Config


def serve_file(
    handler: BaseHTTPRequestHandler,
    path: Path,
    *,
    force_download: bool = False,
    auth_enabled: bool = False,
) -> None:
    """Stream a file to the client in 64 KB chunks, keeping memory flat.

    Args:
        handler: The active request handler.
        path: Resolved path to the file on disk.
        force_download: Force ``Content-Disposition: attachment``.
        auth_enabled: Whether to send ``Cache-Control: no-store``.
    """
    try:
        f = path.open("rb")
    except OSError:
        send_error(handler, 404, "File not found")
        return

    try:
        size = os.fstat(f.fileno()).st_size
        mime_type = get_mime_type(path)
        dtype = "attachment" if force_download or not is_previewable_type(mime_type) else "inline"
        disposition = format_content_disposition(dtype, path.name)

        parsed = _parse_range(handler.headers.get("Range"), size)
        if parsed is _RANGE_INVALID:
            handler.send_response(416)
            handler.send_header("Content-Range", f"bytes */{size}")
            handler.send_header("Content-Length", "0")
            handler.end_headers()
            return

        if parsed is not None:
            start, end = parsed
            length = end - start + 1
            handler.send_response(206)
            handler.send_header("Content-Type", mime_type)
            handler.send_header("Content-Disposition", disposition)
            handler.send_header("Content-Length", str(length))
            handler.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            handler.send_header("Accept-Ranges", "bytes")
            if auth_enabled:
                handler.send_header("Cache-Control", "no-store")
            handler.end_headers()
            f.seek(start)
            _copy_range(f, handler.wfile, length)
            return

        handler.send_response(200)
        handler.send_header("Content-Type", mime_type)
        handler.send_header("Content-Disposition", disposition)
        handler.send_header("Content-Length", str(size))
        handler.send_header("Accept-Ranges", "bytes")
        if auth_enabled:
            handler.send_header("Cache-Control", "no-store")
        handler.end_headers()
        shutil.copyfileobj(f, handler.wfile, length=65536)
    finally:
        f.close()


_RANGE_INVALID: tuple[int, int] = (-1, -1)


def _parse_range(header: str | None, size: int) -> tuple[int, int] | None:  # noqa: PLR0911
    """Parse a single-range ``Range: bytes=...`` header.

    Returns ``None`` if no Range header was sent, ``(start, end)`` inclusive
    for a valid range, or the ``_RANGE_INVALID`` sentinel if the header is
    unsatisfiable (caller should respond 416).

    Supports ``bytes=start-end``, ``bytes=start-``, and ``bytes=-suffix``.
    Multi-range requests (comma-separated) are rejected as invalid —
    single-range coverage is enough for video seek and resumed downloads.
    """
    if not header or not header.startswith("bytes="):
        return None
    spec = header[len("bytes=") :].strip()
    if "," in spec:
        return _RANGE_INVALID
    if "-" not in spec:
        return _RANGE_INVALID
    start_s, end_s = spec.split("-", 1)
    try:
        if start_s == "":
            suffix = int(end_s)
            if suffix <= 0:
                return _RANGE_INVALID
            start = max(0, size - suffix)
            end = size - 1
        else:
            start = int(start_s)
            end = int(end_s) if end_s else size - 1
    except ValueError:
        return _RANGE_INVALID
    if start < 0 or end < start or start >= size:
        return _RANGE_INVALID
    if end >= size:
        end = size - 1
    return start, end


def _copy_range(src: BinaryIO, dst: BinaryIO, length: int, chunk_size: int = 65536) -> None:
    """Copy ``length`` bytes from ``src`` to ``dst`` in chunks."""
    remaining = length
    while remaining > 0:
        buf = src.read(min(chunk_size, remaining))
        if not buf:
            break
        dst.write(buf)
        remaining -= len(buf)


def serve_directory(
    handler: BaseHTTPRequestHandler,
    config: Config,
    request_path: str,
    resolved: Path,
    *,
    auth_enabled: bool = False,
) -> None:
    """Serve an HTML directory listing."""
    entries = list_directory(resolved, config.show_hidden)
    page = render_directory_listing(
        path=resolved,
        entries=entries,
        base_dir=config.directory,
        request_path=request_path,
        auth_enabled=auth_enabled,
        enable_zip_download=config.enable_zip_download,
        enable_upload=config.enable_upload,
        banner=config.banner,
    )
    body = page.encode()
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    if auth_enabled:
        handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def serve_zip(
    handler: BaseHTTPRequestHandler,
    config: Config,
    resolved: Path,
    *,
    auth_enabled: bool = False,
) -> None:
    """Stream a ZIP archive of a directory's contents to the client.

    Headers are flushed up-front with ``Transfer-Encoding: chunked``, then
    the archive is streamed directly into ``wfile``. If ``max_zip_size`` is
    exceeded mid-stream, the response truncates and the event is logged —
    at that point the client has already received a 200, so a 413 is not
    possible.
    """
    if not config.enable_zip_download:
        send_error(handler, 403, "ZIP downloads are disabled")
        return

    zip_name = (resolved.name or "root") + ".zip"

    handler.send_response(200)
    handler.send_header("Content-Type", "application/zip")
    handler.send_header("Transfer-Encoding", "chunked")
    handler.send_header(
        "Content-Disposition",
        format_content_disposition("attachment", zip_name),
    )
    if auth_enabled:
        handler.send_header("Cache-Control", "no-store")
    handler.end_headers()

    try:
        stream_zip(
            handler.wfile,  # type: ignore[arg-type]
            directory=resolved,
            base_dir=config.directory,
            show_hidden=config.show_hidden,
            max_size=config.max_zip_size,
        )
    except ZipSizeLimitError:
        logger.warning("ZIP stream aborted: exceeded max_zip_size=%d", config.max_zip_size)
