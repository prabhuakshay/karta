"""Auth page request handling for neev.

Module-level helpers that accept the active request handler, following the
same pattern as ``server_upload`` and ``server_assets``. Extracted from
``server.py`` to keep the main handler under the line limit.
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, unquote, urlparse

from neev.auth import (
    COOKIE_NAME,
    LoginRateLimiter,
    SessionStore,
    check_credentials,
    parse_cookie,
)
from neev.config import Config
from neev.html_login import render_login_page
from neev.server_utils import send_error
from neev.share import path_in_scope, verify


def check_share_token(handler: BaseHTTPRequestHandler, config: Config) -> bool | None:
    """Validate a ``?share=...`` token against the incoming request.

    Returns ``True`` when the token is valid and the request is within
    the payload's scope and allowed for this HTTP method, ``False`` when
    a token was presented but failed any check (caller should send 403
    and skip the normal auth fallback), or ``None`` when no token was
    presented (caller should run normal auth).
    """
    if config.share_secret is None:
        return None
    parsed = urlparse(handler.path)
    if "share=" not in (parsed.query or ""):
        return None
    query = parse_qs(parsed.query, keep_blank_values=True)
    raw_token = query.get("share", [""])[0]
    payload = verify(raw_token, config.share_secret)
    if payload is None:
        return False
    request_path = unquote(parsed.path)
    if not path_in_scope(request_path, payload.path):
        return False
    return not (handler.command == "POST" and not payload.write_allowed)


def _is_secure_context(handler: BaseHTTPRequestHandler) -> bool:
    """Check whether the request arrived over HTTPS (directly or via proxy)."""
    return handler.headers.get("X-Forwarded-Proto", "").lower() == "https"


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


def handle_login(
    handler: BaseHTTPRequestHandler,
    config: Config,
    sessions: SessionStore,
    rate_limiter: LoginRateLimiter,
) -> None:
    """Process a login form POST and set a session cookie on success.

    Args:
        handler: The active request handler.
        config: The resolved server configuration.
        sessions: Shared session store for auth tokens.
        rate_limiter: Shared rate limiter for login attempts.
    """
    if config.username is None or config.password is None:  # pragma: no cover
        return

    client_ip = handler.client_address[0]

    if rate_limiter.is_blocked(client_ip):
        send_error(handler, 429, "Too many login attempts. Try again later.")
        return

    try:
        content_length = int(handler.headers.get("Content-Length", 0))
    except ValueError:
        send_error(handler, 400, "Invalid Content-Length")
        return

    if content_length < 0 or content_length > 8192:
        send_error(handler, 413, "Request too large")
        return
    raw_body = handler.rfile.read(content_length).decode("utf-8")
    params = parse_qs(raw_body)

    username = params.get("username", [""])[0]
    password = params.get("password", [""])[0]

    if not check_credentials(username, password, config.username, config.password):
        rate_limiter.record_failure(client_ip)
        serve_login_page(handler, error="Invalid username or password.")
        return

    rate_limiter.record_success(client_ip)
    token = sessions.create()
    secure = "; Secure" if _is_secure_context(handler) else ""
    handler.send_response(303)
    handler.send_header("Location", "/")
    handler.send_header(
        "Set-Cookie",
        f"{COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Strict{secure}",
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

    secure = "; Secure" if _is_secure_context(handler) else ""
    handler.send_response(303)
    handler.send_header("Location", "/_neev/login")
    handler.send_header(
        "Set-Cookie",
        f"{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0{secure}",
    )
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
