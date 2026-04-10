"""HTTP server and request handler for karta."""

import importlib.resources
import sys
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from karta.config import Config
from karta.fs import list_directory, read_file, resolve_safe_path
from karta.html import render_directory_listing


# Inline SVG favicon — bold "K" on a teal circle
_FAVICON_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
    b'<circle cx="32" cy="32" r="30" fill="#0d9488"/>'
    b'<text x="32" y="44" font-family="sans-serif" font-size="36" '
    b'font-weight="bold" fill="white" text-anchor="middle">K</text>'
    b"</svg>"
)


# -- ANSI styling for request logs -----------------------------------------


def _log_styled(text: str, code: str) -> str:
    """Wrap text in ANSI escape codes if stderr is a terminal.

    Args:
        text: The string to style.
        code: ANSI SGR code.

    Returns:
        The styled string, or the original text if stderr is not a terminal.
    """
    if not sys.stderr.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def _status_color(status: int) -> str:
    """Return an ANSI-colored status code string.

    Args:
        status: HTTP status code.

    Returns:
        Color-coded status string (green for 2xx, yellow for 3xx, red for 4xx+).
    """
    text = str(status)
    if 200 <= status < 300:
        return _log_styled(text, "32")
    if 300 <= status < 400:
        return _log_styled(text, "33")
    return _log_styled(text, "31")


# -- Request handler -------------------------------------------------------


class KartaHandler(BaseHTTPRequestHandler):
    """HTTP request handler that serves files from a configured directory.

    Config is injected via ``functools.partial`` when creating the handler
    class, since ``HTTPServer`` instantiates the handler per-request.
    """

    def __init__(
        self,
        config: Config,
        request: Any,
        client_address: Any,
        server: HTTPServer,
    ) -> None:
        """Initialize handler with injected config.

        Args:
            config: The resolved server configuration.
            request: The incoming socket request.
            client_address: The ``(host, port)`` of the client.
            server: The parent ``HTTPServer`` instance.
        """
        self.config = config
        super().__init__(request, client_address, server)

    def do_GET(self) -> None:
        """Handle GET requests: serve files, directories, or static assets."""
        if self.path == "/favicon.ico":
            self._serve_favicon()
            return

        if self.path.startswith("/_karta/static/"):
            self._serve_static(self.path)
            return

        request_path = unquote(self.path)
        resolved = resolve_safe_path(self.config.directory, request_path)

        if resolved is None:
            self._send_error(403, "Forbidden")
            return

        if not resolved.exists():
            self._send_error(404, "Not Found")
            return

        if resolved.is_dir():
            self._serve_directory(request_path, resolved)
            return

        self._serve_file(resolved)

    def _serve_file(self, path: Path) -> None:
        """Serve a file with correct Content-Type and Content-Length.

        Args:
            path: Resolved filesystem path to the file.
        """
        content, content_type = read_file(path)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_directory(self, request_path: str, resolved: Path) -> None:
        """Serve an HTML directory listing.

        Args:
            request_path: The original URL path.
            resolved: The resolved filesystem path.
        """
        entries = list_directory(resolved, self.config.show_hidden)
        page = render_directory_listing(
            path=resolved,
            entries=entries,
            base_dir=self.config.directory,
            request_path=request_path,
        )
        body = page.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, url_path: str) -> None:
        """Serve bundled static assets from the karta package.

        Args:
            url_path: The full URL path starting with ``/_karta/static/``.
        """
        filename = url_path.removeprefix("/_karta/static/")
        if not filename or "/" in filename:
            self._send_error(404, "Not Found")
            return

        mime_types = {
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
        }

        try:
            ref = importlib.resources.files("karta").joinpath("static", filename)
            content = ref.read_bytes()
        except (FileNotFoundError, TypeError):
            self._send_error(404, "Not Found")
            return

        suffix = Path(filename).suffix
        content_type = mime_types.get(suffix, "application/octet-stream")

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(content)

    def _serve_favicon(self) -> None:
        """Serve the embedded SVG favicon without logging the request."""
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml")
        self.send_header("Content-Length", str(len(_FAVICON_SVG)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(_FAVICON_SVG)

    def _send_error(self, code: int, message: str) -> None:
        """Send an error response with a plain-text body.

        Args:
            code: HTTP status code.
            message: Human-readable error message.
        """
        body = message.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_request(self, code: int | str = "-", size: int | str = 0) -> None:
        """Log a request with colored output to stderr.

        Favicon requests are suppressed to reduce log noise.

        Args:
            code: HTTP status code.
            size: Response size (unused, kept for API compatibility).
        """
        if self.path == "/favicon.ico":
            return
        method = _log_styled(self.command or "?", "1")
        path = _log_styled(self.path, "36")
        status = _status_color(int(code)) if str(code).isdigit() else str(code)
        print(f"  {method} {path} {status}", file=sys.stderr)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Suppress default BaseHTTPRequestHandler logging.

        All logging goes through ``log_request`` instead.

        Args:
            format: Printf-style format string (ignored).
            *args: Format arguments (ignored).
        """


# -- Server startup --------------------------------------------------------


def run_server(config: Config) -> None:
    """Start the HTTP server and block until interrupted.

    Creates an ``HTTPServer`` with ``KartaHandler`` configured via
    ``functools.partial``, then serves requests until ``KeyboardInterrupt``.

    Args:
        config: The resolved server configuration.
    """
    handler = partial(KartaHandler, config)
    server = HTTPServer((config.host, config.port), handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
