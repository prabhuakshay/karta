"""Selective ZIP download handler for neev.

Handles POST requests with selected item names, creates a ZIP of those items,
and streams it to the client.
"""

import shutil
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, unquote

from neev.fs import format_content_disposition, resolve_safe_path
from neev.server_utils import send_error
from neev.zip import ZipSizeLimitError, create_selective_zip_stream


if TYPE_CHECKING:
    from neev.config import Config
    from neev.server import NeevHandler


def _is_unsafe_item(name: str) -> bool:
    """Reject item names that contain path separators, traversal, or are empty."""
    if not name or not name.strip():
        return True
    if "/" in name or "\\" in name:
        return True
    return name in {".", ".."}


def serve_selective_zip(handler: "NeevHandler", request_path: str) -> None:  # noqa: PLR0911 -- sequential input validation, each failure returns early
    """Handle a POST request to download selected items as a ZIP.

    Reads selected item names from the POST body (``items=name`` form fields),
    creates a ZIP containing only those items, and streams it.

    Args:
        handler: The HTTP request handler.
        request_path: The URL-decoded request path.
    """
    config: Config = handler.config
    if not config.enable_zip_download:
        send_error(handler, 403, b"ZIP downloads are disabled")
        return

    try:
        content_length = int(handler.headers.get("Content-Length", 0))
    except ValueError:
        send_error(handler, 400, b"Invalid Content-Length")
        return

    if content_length <= 0 or content_length > 65536:
        send_error(handler, 400, b"Invalid request body")
        return

    raw_body = handler.rfile.read(content_length).decode("utf-8", errors="replace")
    parsed = parse_qs(raw_body)
    items = [unquote(i) for i in parsed.get("items", [])]

    if not items:
        send_error(handler, 400, b"No items selected")
        return

    if any(_is_unsafe_item(name) for name in items):
        send_error(handler, 400, b"Invalid item name")
        return

    resolved = resolve_safe_path(config.directory, request_path)
    if resolved is None or not resolved.is_dir():
        send_error(handler, 404, b"Directory not found")
        return

    zip_name = (resolved.name or "root") + "-selected.zip"
    try:
        stream = create_selective_zip_stream(
            directory=resolved,
            items=items,
            base_dir=config.directory,
            show_hidden=config.show_hidden,
            max_size=config.max_zip_size,
        )
    except ZipSizeLimitError:
        send_error(handler, 413, b"ZIP archive too large")
        return

    size = stream.seek(0, 2)
    stream.seek(0)

    handler.send_response(200)
    handler.send_header("Content-Type", "application/zip")
    handler.send_header("Content-Length", str(size))
    handler.send_header(
        "Content-Disposition",
        format_content_disposition("attachment", zip_name),
    )
    handler.end_headers()
    shutil.copyfileobj(stream, handler.wfile)
