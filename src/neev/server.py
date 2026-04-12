"""HTTP server and request handler for neev."""

import sys
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse, urlsplit

from neev.auth import (
    COOKIE_NAME,
    LoginRateLimiter,
    SessionStore,
    check_basic_auth,
    parse_cookie,
)
from neev.config import Config
from neev.fs import get_mime_type, is_markdown_file, is_previewable_type, resolve_safe_path
from neev.log import ansi_styled, status_color
from neev.server_assets import serve_favicon, serve_static
from neev.server_auth import handle_login, handle_logout, serve_login_page
from neev.server_core import serve_directory, serve_file, serve_zip
from neev.server_preview import serve_generic_preview, serve_markdown_preview
from neev.server_upload import serve_mkdir, serve_upload
from neev.server_utils import send_error
from neev.server_zip import serve_selective_zip


# -- Request handler -------------------------------------------------------


class NeevHandler(BaseHTTPRequestHandler):
    """HTTP request handler that serves files from a configured directory.

    Config and session store are injected via ``functools.partial`` when
    creating the handler class, since ``HTTPServer`` instantiates the
    handler per-request.
    """

    def __init__(
        self,
        config: Config,
        sessions: SessionStore,
        rate_limiter: LoginRateLimiter,
        request: Any,
        client_address: Any,
        server: HTTPServer,
    ) -> None:
        """Initialize handler with injected config and session store.

        Args:
            config: The resolved server configuration.
            sessions: Shared session store for auth tokens.
            rate_limiter: Shared rate limiter for login attempts.
            request: The incoming socket request.
            client_address: The ``(host, port)`` of the client.
            server: The parent ``HTTPServer`` instance.
        """
        self.config = config
        self.sessions = sessions
        self.rate_limiter = rate_limiter
        super().__init__(request, client_address, server)

    # -- Auth ----------------------------------------------------------------

    def _is_authenticated(self) -> bool:
        """Check if the request has valid credentials via session or header.

        Supports two auth paths:
        - **Cookie session** (browsers): ``neev_session`` cookie
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

        self._redirect("/_neev/login")
        return False

    def _check_origin(self) -> bool:
        """Reject cross-origin POST requests (CSRF defense).

        Compares the Origin (or Referer) header against the Host header.
        Requests with no Origin/Referer are allowed — they come from
        curl/API clients, not browsers.

        Returns:
            ``True`` if the request may proceed, ``False`` if blocked.
        """
        origin = self.headers.get("Origin")
        source = origin if origin is not None else self.headers.get("Referer")
        if source is None:
            return True

        parts = urlsplit(source)
        if not parts.scheme or not parts.netloc:
            self._send_error(400, "Bad Request - malformed Origin/Referer")
            return False

        host = self.headers.get("Host", "")
        if parts.netloc == host:
            return True

        self._send_error(403, "Forbidden - origin mismatch")
        return False

    def _send_401(self) -> None:
        """Send a 401 for API/curl clients using the Authorization header."""
        body = b"401 Unauthorized"
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="neev"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # -- Routing -------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: PLR0911 -- router: each branch is a distinct route
        """Handle GET requests: auth pages, files, directories, static."""
        if self.config.auth_enabled and self.path == "/_neev/login":
            self._serve_login_page()
            return

        if self.config.auth_enabled and self.path == "/_neev/logout":
            self._handle_logout()
            return

        if not self._check_auth():
            return

        if self.path == "/favicon.svg":
            serve_favicon(self)
            return

        if self.path.startswith("/_neev/static/"):
            serve_static(self, self.path)
            return

        parsed = urlparse(self.path)
        request_path = unquote(parsed.path)
        wants_zip = parsed.query == "zip"
        resolved = resolve_safe_path(self.config.directory, request_path)

        if resolved is None:
            self._send_error(403, "Forbidden")
            return

        if not resolved.exists():
            self._send_error(404, "Not Found")
            return

        auth = self.config.auth_enabled

        if resolved.is_dir() and wants_zip:
            serve_zip(self, self.config, resolved, auth_enabled=auth)
            return

        if resolved.is_dir():
            serve_directory(self, self.config, request_path, resolved, auth_enabled=auth)
            return

        if parsed.query == "preview" and is_markdown_file(resolved):
            serve_markdown_preview(self, resolved, request_path)
            return

        if parsed.query == "preview":
            mime = get_mime_type(resolved)
            if is_previewable_type(mime):
                serve_generic_preview(self, resolved, request_path, mime)
                return

        serve_file(self, resolved, force_download=parsed.query == "download", auth_enabled=auth)

    def do_POST(self) -> None:
        """Handle POST requests: login, file uploads, folder creation."""
        if not self._check_origin():
            return

        if self.config.auth_enabled and self.path == "/_neev/login":
            self._handle_login()
            return

        if not self._check_auth():
            return

        parsed = urlparse(self.path)
        request_path = unquote(parsed.path)
        query = parse_qs(parsed.query)

        if parsed.query == "zip":
            serve_selective_zip(self, request_path)
            return

        if "mkdir" in query:
            self._handle_mkdir(request_path, query)
            return

        self._handle_upload(request_path)

    # -- Auth pages ----------------------------------------------------------

    def _serve_login_page(self, error: str | None = None) -> None:
        """Serve the login form page."""
        serve_login_page(self, error)

    def _handle_login(self) -> None:
        """Process a login form POST and set a session cookie on success."""
        handle_login(self, self.config, self.sessions, self.rate_limiter)

    def _handle_logout(self) -> None:
        """Invalidate the session and redirect to the login page."""
        handle_logout(self, self.sessions)

    # -- Uploads -------------------------------------------------------------

    def _handle_upload(self, request_path: str) -> None:
        """Handle a file upload POST request."""
        serve_upload(self, self.config.directory, self.config.enable_upload, request_path)

    def _handle_mkdir(self, request_path: str, query: dict[str, list[str]]) -> None:
        """Handle a create-folder POST request."""
        serve_mkdir(self, self.config.directory, self.config.enable_upload, request_path, query)

    # -- Helpers -------------------------------------------------------------

    def _redirect(self, location: str) -> None:
        """Send a 303 See Other redirect."""
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def _cache_header(self) -> None:
        """Set Cache-Control: no-store when auth is enabled."""
        if self.config.auth_enabled:
            self.send_header("Cache-Control", "no-store")

    def _send_error(self, code: int, message: str) -> None:
        """Send an error response with a plain-text body."""
        send_error(self, code, message)

    # -- Logging -------------------------------------------------------------

    def log_request(self, code: int | str = "-", size: int | str = 0) -> None:
        """Log a request with colored output to stderr."""
        if self.path == "/favicon.svg":
            return
        method = ansi_styled(self.command or "?", "1")
        path = ansi_styled(self.path, "36")
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
    rate_limiter = LoginRateLimiter()
    handler = partial(NeevHandler, config, sessions, rate_limiter)
    server = HTTPServer((config.host, config.port), handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
