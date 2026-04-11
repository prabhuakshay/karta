"""HTTP server and request handler for karta."""

import sys
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

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
from karta.server_assets import serve_favicon, serve_static
from karta.upload import MAX_UPLOAD_SIZE, UploadError, handle_create_folder, handle_upload
from karta.zip import ZipSizeLimitError, create_zip_bytes


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
            serve_favicon(self)
            return

        if self.path.startswith("/_karta/static/"):
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

        if resolved.is_dir() and wants_zip:
            self._serve_zip(resolved)
            return

        if resolved.is_dir():
            self._serve_directory(request_path, resolved)
            return

        self._serve_file(resolved)

    def do_POST(self) -> None:
        """Handle POST requests: login, file uploads, folder creation."""
        if self._auth_enabled() and self.path == "/_karta/login":
            self._handle_login()
            return

        if not self._check_auth():
            return

        parsed = urlparse(self.path)
        request_path = unquote(parsed.path)
        query = parse_qs(parsed.query)

        if "mkdir" in query:
            self._handle_mkdir(request_path, query)
            return

        self._handle_upload(request_path)

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

    # -- Uploads -------------------------------------------------------------

    def _handle_upload(self, request_path: str) -> None:
        """Handle a file upload POST request."""
        if not self.config.enable_upload:
            self._send_error(403, "Uploads are disabled")
            return

        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            self._send_error(400, "Content-Length required")
            return

        content_length = int(raw_length)
        if content_length > MAX_UPLOAD_SIZE:
            self._send_error(413, "Upload too large")
            return

        content_type = self.headers.get("Content-Type", "")
        resolved = resolve_safe_path(self.config.directory, request_path)
        if resolved is None or not resolved.is_dir():
            self._send_error(400, "Invalid upload target")
            return

        body = self.rfile.read(content_length)
        try:
            handle_upload(body, content_type, content_length, resolved, self.config.directory)
        except UploadError as exc:
            self._send_error(400, str(exc))
            return

        self._redirect(request_path)

    def _handle_mkdir(self, request_path: str, query: dict[str, list[str]]) -> None:
        """Handle a create-folder POST request."""
        if not self.config.enable_upload:
            self._send_error(403, "Uploads are disabled")
            return

        folder_name = query.get("mkdir", [""])[0]
        if not folder_name:  # pragma: no cover — parse_qs drops blank values
            self._send_error(400, "Folder name required")
            return

        resolved = resolve_safe_path(self.config.directory, request_path)
        if resolved is None or not resolved.is_dir():
            self._send_error(400, "Invalid target directory")
            return

        try:
            handle_create_folder(folder_name, resolved, self.config.directory)
        except UploadError as exc:
            self._send_error(400, str(exc))
            return

        self._redirect(request_path)

    # -- Helpers -------------------------------------------------------------

    def _redirect(self, location: str) -> None:
        """Send a 303 See Other redirect."""
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def _cache_header(self) -> None:
        """Set Cache-Control: no-store when auth is enabled."""
        if self._auth_enabled():
            self.send_header("Cache-Control", "no-store")

    def _serve_file(self, path: Path) -> None:
        """Serve a file with correct Content-Type and Content-Length."""
        content, content_type = read_file(path)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self._cache_header()
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
            enable_zip_download=self.config.enable_zip_download,
            enable_upload=self.config.enable_upload,
        )
        body = page.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cache_header()
        self.end_headers()
        self.wfile.write(body)

    def _serve_zip(self, resolved: Path) -> None:
        """Serve a ZIP archive of a directory's contents."""
        if not self.config.enable_zip_download:
            self._send_error(403, "ZIP downloads are disabled")
            return

        dir_name = resolved.name or "root"
        try:
            data = create_zip_bytes(
                directory=resolved,
                base_dir=self.config.directory,
                show_hidden=self.config.show_hidden,
                max_size=self.config.max_zip_size,
            )
        except ZipSizeLimitError:
            self._send_error(413, "ZIP archive too large")
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(len(data)))
        self.send_header(
            "Content-Disposition",
            f'attachment; filename="{dir_name}.zip"',
        )
        self._cache_header()
        self.end_headers()
        self.wfile.write(data)

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
