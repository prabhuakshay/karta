"""HTTP server and request handler for karta."""

import importlib.resources
import sys
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote

from karta.auth import (
    COOKIE_NAME,
    SessionStore,
    check_basic_auth,
    check_credentials,
    parse_cookie,
)
from karta.config import Config
from karta.fs import list_directory, read_file, resolve_safe_path
from karta.html import render_directory_listing
from karta.html_login import render_login_page
from karta.log import log_styled, status_color


# Inline SVG favicon — bold "K" on a teal circle
_FAVICON_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
    b'<circle cx="32" cy="32" r="30" fill="#0d9488"/>'
    b'<text x="32" y="44" font-family="sans-serif" font-size="36" '
    b'font-weight="bold" fill="white" text-anchor="middle">K</text>'
    b"</svg>"
)


# -- Request handler -------------------------------------------------------


class KartaHandler(BaseHTTPRequestHandler):
    """HTTP request handler that serves files from a configured directory.

    Config and session store are injected via ``functools.partial`` when
    creating the handler class, since ``HTTPServer`` instantiates the
    handler per-request.
    """

    def __init__(
        self,
        config: Config,
        sessions: SessionStore,
        request: Any,
        client_address: Any,
        server: HTTPServer,
    ) -> None:
        """Initialize handler with injected config and session store.

        Args:
            config: The resolved server configuration.
            sessions: Shared session store for auth tokens.
            request: The incoming socket request.
            client_address: The ``(host, port)`` of the client.
            server: The parent ``HTTPServer`` instance.
        """
        self.config = config
        self.sessions = sessions
        super().__init__(request, client_address, server)

    # -- Auth ----------------------------------------------------------------

    def _auth_enabled(self) -> bool:
        """Check whether auth is configured."""
        return self.config.username is not None and self.config.password is not None

    def _is_authenticated(self) -> bool:
        """Check if the request has valid credentials via session or header.

        Supports two auth paths:
        - **Cookie session** (browsers): ``karta_session`` cookie
        - **Authorization header** (curl/API): ``Basic`` scheme
        """
        if self.config.username is None or self.config.password is None:
            return True

        cookie_header = self.headers.get("Cookie")
        token = parse_cookie(cookie_header, COOKIE_NAME)
        if token and self.sessions.validate(token):
            return True

        header = self.headers.get("Authorization")
        return check_basic_auth(header, self.config.username, self.config.password)

    def _check_auth(self) -> bool:
        """Gate a request behind auth. Redirects to login if unauthorized.

        Returns:
            ``True`` if the request may proceed. ``False`` if a redirect
            or 401 was sent (caller should return immediately).
        """
        if self._is_authenticated():
            return True

        if self.headers.get("Authorization"):
            self._send_401()
            return False

        self._redirect("/_karta/login")
        return False

    def _send_401(self) -> None:
        """Send a 401 for API/curl clients using the Authorization header."""
        body = b"401 Unauthorized"
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="karta"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # -- Routing -------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: PLR0911
        """Handle GET requests: auth pages, files, directories, static."""
        if self._auth_enabled() and self.path == "/_karta/login":
            self._serve_login_page()
            return

        if self._auth_enabled() and self.path == "/_karta/logout":
            self._handle_logout()
            return

        if not self._check_auth():
            return

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

    def do_POST(self) -> None:
        """Handle POST requests: login form submission."""
        if self._auth_enabled() and self.path == "/_karta/login":
            self._handle_login()
            return

        self._send_error(405, "Method Not Allowed")

    # -- Auth pages ----------------------------------------------------------

    def _serve_login_page(self, error: str | None = None) -> None:
        """Serve the login form page."""
        body = render_login_page(error=error).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _handle_login(self) -> None:
        """Process a login form POST and set a session cookie on success."""
        if self.config.username is None or self.config.password is None:  # pragma: no cover
            return

        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length).decode("utf-8")
        params = parse_qs(raw_body)

        username = params.get("username", [""])[0]
        password = params.get("password", [""])[0]

        if not check_credentials(username, password, self.config.username, self.config.password):
            self._serve_login_page(error="Invalid username or password.")
            return

        token = self.sessions.create()
        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header(
            "Set-Cookie",
            f"{COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Strict",
        )
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _handle_logout(self) -> None:
        """Invalidate the session and redirect to the login page."""
        cookie_header = self.headers.get("Cookie")
        token = parse_cookie(cookie_header, COOKIE_NAME)
        if token:
            self.sessions.invalidate(token)

        self.send_response(303)
        self.send_header("Location", "/_karta/login")
        self.send_header(
            "Set-Cookie",
            f"{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0",
        )
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    # -- Helpers -------------------------------------------------------------

    def _redirect(self, location: str) -> None:
        """Send a 303 See Other redirect."""
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def _serve_file(self, path: Path) -> None:
        """Serve a file with correct Content-Type and Content-Length."""
        content, content_type = read_file(path)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_directory(self, request_path: str, resolved: Path) -> None:
        """Serve an HTML directory listing."""
        entries = list_directory(resolved, self.config.show_hidden)
        page = render_directory_listing(
            path=resolved,
            entries=entries,
            base_dir=self.config.directory,
            request_path=request_path,
            auth_enabled=self._auth_enabled(),
        )
        body = page.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, url_path: str) -> None:
        """Serve bundled static assets from the karta package."""
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
        """Serve the embedded SVG favicon."""
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml")
        self.send_header("Content-Length", str(len(_FAVICON_SVG)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(_FAVICON_SVG)

    def _send_error(self, code: int, message: str) -> None:
        """Send an error response with a plain-text body."""
        body = message.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # -- Logging -------------------------------------------------------------

    def log_request(self, code: int | str = "-", size: int | str = 0) -> None:
        """Log a request with colored output to stderr."""
        if self.path == "/favicon.ico":
            return
        method = log_styled(self.command or "?", "1")
        path = log_styled(self.path, "36")
        status = status_color(int(code)) if str(code).isdigit() else str(code)
        print(f"  {method} {path} {status}", file=sys.stderr)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Suppress default BaseHTTPRequestHandler logging."""


# -- Server startup --------------------------------------------------------


def run_server(config: Config) -> None:
    """Start the HTTP server and block until interrupted.

    Args:
        config: The resolved server configuration.
    """
    sessions = SessionStore()
    handler = partial(KartaHandler, config, sessions)
    server = HTTPServer((config.host, config.port), handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
