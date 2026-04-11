"""Auth page request handling for karta.

Module-level helpers that accept the active request handler, following the
same pattern as ``server_upload`` and ``server_assets``. Extracted from
``server.py`` to keep the main handler under the line limit.
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs

from karta.auth import COOKIE_NAME, SessionStore, check_credentials, parse_cookie
from karta.config import Config
from karta.html_login import render_login_page


def serve_login_page(handler: BaseHTTPRequestHandler, error: str | None = None) -> None:
    """Serve the login form page.

    Args:
        handler: The active request handler.
        error: Optional error message to display on the form.
    """
    body = render_login_page(error=error).encode()
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def handle_login(handler: BaseHTTPRequestHandler, config: Config, sessions: SessionStore) -> None:
    """Process a login form POST and set a session cookie on success.

    Args:
        handler: The active request handler.
        config: The resolved server configuration.
        sessions: Shared session store for auth tokens.
    """
    if config.username is None or config.password is None:  # pragma: no cover
        return

    content_length = int(handler.headers.get("Content-Length", 0))
    if content_length < 0 or content_length > 8192:
        _send_error(handler, 413, "Request too large")
        return
    raw_body = handler.rfile.read(content_length).decode("utf-8")
    params = parse_qs(raw_body)

    username = params.get("username", [""])[0]
    password = params.get("password", [""])[0]

    if not check_credentials(username, password, config.username, config.password):
        serve_login_page(handler, error="Invalid username or password.")
        return

    token = sessions.create()
    handler.send_response(303)
    handler.send_header("Location", "/")
    handler.send_header(
        "Set-Cookie",
        f"{COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Strict",
    )
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()


def handle_logout(handler: BaseHTTPRequestHandler, sessions: SessionStore) -> None:
    """Invalidate the session and redirect to the login page.

    Args:
        handler: The active request handler.
        sessions: Shared session store for auth tokens.
    """
    cookie_header = handler.headers.get("Cookie")
    token = parse_cookie(cookie_header, COOKIE_NAME)
    if token:
        sessions.invalidate(token)

    handler.send_response(303)
    handler.send_header("Location", "/_karta/login")
    handler.send_header(
        "Set-Cookie",
        f"{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0",
    )
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()


def _send_error(handler: BaseHTTPRequestHandler, code: int, message: str) -> None:
    body = message.encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)
