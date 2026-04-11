"""Upload and folder-creation request handling for neev.

Module-level helpers that accept the active request handler, following the
same pattern as ``server_assets``. Extracted from ``server.py`` to keep the
main handler under the line limit.
"""

from http.server import BaseHTTPRequestHandler
from pathlib import Path

from neev.fs import resolve_safe_path
from neev.upload import MAX_UPLOAD_SIZE, UploadError, handle_create_folder, handle_upload


def serve_upload(
    handler: BaseHTTPRequestHandler,
    directory: Path,
    enable_upload: bool,
    request_path: str,
) -> None:
    """Handle a file upload POST request.

    Args:
        handler: The active request handler.
        directory: The served root directory (security boundary).
        enable_upload: Whether uploads are enabled.
        request_path: The URL path to the target directory.
    """
    if not enable_upload:
        _send_error(handler, 403, "Uploads are disabled")
        return

    raw_length = handler.headers.get("Content-Length")
    if raw_length is None:
        _send_error(handler, 400, "Content-Length required")
        return

    try:
        content_length = int(raw_length)
    except ValueError:
        _send_error(handler, 400, "Invalid Content-Length")
        return

    if content_length > MAX_UPLOAD_SIZE:
        _send_error(handler, 413, "Upload too large")
        return

    content_type = handler.headers.get("Content-Type", "")
    resolved = resolve_safe_path(directory, request_path)
    if resolved is None or not resolved.is_dir():
        _send_error(handler, 400, "Invalid upload target")
        return

    body = handler.rfile.read(content_length)
    try:
        handle_upload(body, content_type, content_length, resolved, directory)
    except UploadError as exc:
        _send_error(handler, 400, str(exc))
        return

    _redirect(handler, request_path)


def serve_mkdir(
    handler: BaseHTTPRequestHandler,
    directory: Path,
    enable_upload: bool,
    request_path: str,
    query: dict[str, list[str]],
) -> None:
    """Handle a create-folder POST request.

    Args:
        handler: The active request handler.
        directory: The served root directory (security boundary).
        enable_upload: Whether uploads are enabled.
        request_path: The URL path to the target directory.
        query: Parsed query parameters from the request URL.
    """
    if not enable_upload:
        _send_error(handler, 403, "Uploads are disabled")
        return

    folder_name = query.get("mkdir", [""])[0]
    if not folder_name:  # pragma: no cover — parse_qs drops blank values
        _send_error(handler, 400, "Folder name required")
        return

    resolved = resolve_safe_path(directory, request_path)
    if resolved is None or not resolved.is_dir():
        _send_error(handler, 400, "Invalid target directory")
        return

    try:
        handle_create_folder(folder_name, resolved, directory)
    except UploadError as exc:
        _send_error(handler, 400, str(exc))
        return

    _redirect(handler, request_path)


def _send_error(handler: BaseHTTPRequestHandler, code: int, message: str) -> None:
    body = message.encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _redirect(handler: BaseHTTPRequestHandler, location: str) -> None:
    handler.send_response(303)
    handler.send_header("Location", location)
    handler.end_headers()
