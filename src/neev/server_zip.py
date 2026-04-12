"""Selective ZIP download handler for neev.

Handles POST requests with selected item names, creates a ZIP of those items,
and streams it to the client.
"""

import logging
from http.server import BaseHTTPRequestHandler
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, unquote

from neev.fs import format_content_disposition, resolve_safe_path
from neev.zip import ZipSizeLimitError, stream_selective_zip


logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from neev.config import Config
    from neev.server import NeevHandler


def _send_text(handler: BaseHTTPRequestHandler, status: int, message: bytes) -> None:
    """Send a plain-text error response."""
    handler.send_response(status)
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    handler.send_header("Content-Length", str(len(message)))
    handler.end_headers()
    handler.wfile.write(message)


def serve_selective_zip(handler: "NeevHandler", request_path: str) -> None:
    """Handle a POST request to download selected items as a ZIP.

    Reads selected item names from the POST body (``items=name`` form fields),
    creates a ZIP containing only those items, and streams it.

    Args:
        handler: The HTTP request handler.
        request_path: The URL-decoded request path.
    """
    config: Config = handler.config
    if not config.enable_zip_download:
        _send_text(handler, 403, b"ZIP downloads are disabled")
        return

    try:
        content_length = int(handler.headers.get("Content-Length", 0))
    except ValueError:
        _send_text(handler, 400, b"Invalid Content-Length")
        return

    if content_length <= 0 or content_length > 65536:
        _send_text(handler, 400, b"Invalid request body")
        return

    raw_body = handler.rfile.read(content_length).decode("utf-8", errors="replace")
    parsed = parse_qs(raw_body)
    items = [unquote(i) for i in parsed.get("items", [])]

    if not items:
        _send_text(handler, 400, b"No items selected")
        return

    resolved = resolve_safe_path(config.directory, request_path)
    if resolved is None or not resolved.is_dir():
        _send_text(handler, 404, b"Directory not found")
        return

    zip_name = (resolved.name or "root") + "-selected.zip"

    handler.send_response(200)
    handler.send_header("Content-Type", "application/zip")
    handler.send_header("Transfer-Encoding", "chunked")
    handler.send_header(
        "Content-Disposition",
        format_content_disposition("attachment", zip_name),
    )
    handler.end_headers()

    try:
        stream_selective_zip(
            handler.wfile,  # type: ignore[arg-type]
            directory=resolved,
            items=items,
            base_dir=config.directory,
            show_hidden=config.show_hidden,
            max_size=config.max_zip_size,
        )
    except ZipSizeLimitError:
        logger.warning("selective ZIP aborted: exceeded max_zip_size=%d", config.max_zip_size)
