"""Static asset serving for neev.

Handles bundled CSS/JS files, the favicon, and cache headers.
Extracted from ``server.py`` to keep the main handler under the line limit.
"""

import importlib.resources
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from neev.server_utils import send_error


# Inline SVG favicon — bold "N" on a teal circle
FAVICON_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
    b'<circle cx="32" cy="32" r="30" fill="#0d9488"/>'
    b'<text x="32" y="44" font-family="sans-serif" font-size="36" '
    b'font-weight="bold" fill="white" text-anchor="middle">N</text>'
    b"</svg>"
)

_STATIC_MIME = {
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}

_asset_cache: dict[str, bytes] = {}


def serve_static(handler: BaseHTTPRequestHandler, url_path: str) -> None:
    """Serve bundled static assets from the neev package.

    Args:
        handler: The active request handler (for sending response).
        url_path: The full URL path (e.g. ``/_neev/static/neev.css``).
    """
    filename = url_path.removeprefix("/_neev/static/")
    if not filename or "/" in filename:
        send_error(handler, 404, "Not Found")
        return

    try:
        if filename not in _asset_cache:
            ref = importlib.resources.files("neev").joinpath("static", filename)
            _asset_cache[filename] = ref.read_bytes()
        content = _asset_cache[filename]
    except (FileNotFoundError, TypeError):
        send_error(handler, 404, "Not Found")
        return

    suffix = Path(filename).suffix
    content_type = _STATIC_MIME.get(suffix, "application/octet-stream")

    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(content)))
    handler.send_header("Cache-Control", "public, max-age=86400")
    handler.end_headers()
    handler.wfile.write(content)


def serve_favicon(handler: BaseHTTPRequestHandler) -> None:
    """Serve the embedded SVG favicon.

    Args:
        handler: The active request handler.
    """
    handler.send_response(200)
    handler.send_header("Content-Type", "image/svg+xml")
    handler.send_header("Content-Length", str(len(FAVICON_SVG)))
    handler.send_header("Cache-Control", "public, max-age=86400")
    handler.end_headers()
    handler.wfile.write(FAVICON_SVG)
