"""Core file and directory serving handlers for neev.

Handles serving individual files, directory listings, and ZIP downloads.
Each function follows the delegation pattern: the ``NeevHandler`` instance
is passed as the first argument.
"""

from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING

from neev.fs import (
    format_content_disposition,
    get_mime_type,
    is_previewable_type,
    list_directory,
)
from neev.html import render_directory_listing
from neev.zip import ZipSizeLimitError, create_zip_stream


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
        _send_error(handler, 404, "File not found")
        return

    try:
        size = os.fstat(f.fileno()).st_size
        mime_type = get_mime_type(path)
        dtype = "attachment" if force_download or not is_previewable_type(mime_type) else "inline"
        disposition = format_content_disposition(dtype, path.name)

        handler.send_response(200)
        handler.send_header("Content-Type", mime_type)
        handler.send_header("Content-Disposition", disposition)
        handler.send_header("Content-Length", str(size))
        if auth_enabled:
            handler.send_header("Cache-Control", "no-store")
        handler.end_headers()
        shutil.copyfileobj(f, handler.wfile, length=65536)
    finally:
        f.close()


def serve_directory(
    handler: BaseHTTPRequestHandler,
    config: Config,
    request_path: str,
    resolved: Path,
    *,
    auth_enabled: bool = False,
) -> None:
    """Serve an HTML directory listing.

    Args:
        handler: The active request handler.
        config: The resolved server configuration.
        request_path: The original URL path from the request.
        resolved: Resolved path to the directory on disk.
        auth_enabled: Whether to show the logout button and suppress caching.
    """
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
    """Serve a ZIP archive of a directory's contents.

    Args:
        handler: The active request handler.
        config: The resolved server configuration.
        resolved: Resolved path to the directory on disk.
        auth_enabled: Whether to send ``Cache-Control: no-store``.
    """
    if not config.enable_zip_download:
        _send_error(handler, 403, "ZIP downloads are disabled")
        return

    zip_name = (resolved.name or "root") + ".zip"
    try:
        stream = create_zip_stream(
            directory=resolved,
            base_dir=config.directory,
            show_hidden=config.show_hidden,
            max_size=config.max_zip_size,
        )
    except ZipSizeLimitError:
        _send_error(handler, 413, "ZIP archive too large")
        return

    # Compute size by seeking to end — avoids getvalue() second copy.
    size = stream.seek(0, 2)
    stream.seek(0)

    handler.send_response(200)
    handler.send_header("Content-Type", "application/zip")
    handler.send_header("Content-Length", str(size))
    handler.send_header(
        "Content-Disposition",
        format_content_disposition("attachment", zip_name),
    )
    if auth_enabled:
        handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    shutil.copyfileobj(stream, handler.wfile)


def _send_error(handler: BaseHTTPRequestHandler, code: int, message: str) -> None:
    """Send an error response with a plain-text body."""
    body = message.encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)
