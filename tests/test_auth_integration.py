"""Integration tests for the karta auth flow — login, logout, session cookies."""

import base64
import threading
import urllib.error
from functools import partial
from http.server import HTTPServer
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

import pytest

from karta.auth import COOKIE_NAME, SessionStore
from karta.config import Config
from karta.server import KartaHandler


# -- Fixtures ----------------------------------------------------------------


@pytest.fixture
def auth_serve_dir(tmp_path):
    """Create a temp directory with a test file."""
    (tmp_path / "secret.txt").write_text("top secret")
    return tmp_path


@pytest.fixture
def auth_config(auth_serve_dir):
    """Config with auth enabled."""
    return Config(
        directory=auth_serve_dir,
        host="127.0.0.1",
        port=0,
        username="alice",
        password="secret",
        show_hidden=False,
        enable_zip_download=False,
        max_zip_size=104857600,
        enable_upload=False,
    )


@pytest.fixture
def auth_server(auth_config):
    """Start a server with auth enabled, yield base URL."""
    sessions = SessionStore()
    handler = partial(KartaHandler, auth_config, sessions)
    httpd = HTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()
    httpd.server_close()


# -- HTTP helpers ------------------------------------------------------------


class _NoRedirect(HTTPRedirectHandler):
    """Prevent urlopen from following redirects so tests can inspect 3xx."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)


_opener = build_opener(_NoRedirect)


def _request(
    url: str,
    path: str = "/",
    method: str = "GET",
    auth: tuple[str, str] | None = None,
    cookie: str | None = None,
    body: bytes | None = None,
    content_type: str | None = None,
) -> tuple[int, dict[str, str], bytes]:
    """Make an HTTP request without following redirects."""
    req = Request(f"{url}{path}", method=method)
    if auth:
        creds = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        req.add_header("Authorization", f"Basic {creds}")
    if cookie:
        req.add_header("Cookie", cookie)
    if body is not None:
        req.data = body
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        resp = _opener.open(req)
        return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()
    except Exception as exc:
        if hasattr(exc, "code"):
            return exc.code, dict(exc.headers), exc.read()  # type: ignore[attr-defined]
        raise


# -- Integration tests -------------------------------------------------------


class TestAuthRedirect:
    def test_unauthenticated_redirects_to_login(self, auth_server):
        status, headers, _ = _request(auth_server, "/")
        assert status == 303
        assert headers["Location"] == "/_karta/login"

    def test_login_page_accessible_without_auth(self, auth_server):
        status, headers, body = _request(auth_server, "/_karta/login")
        assert status == 200
        assert b"Sign in" in body
        assert headers["Content-Type"] == "text/html; charset=utf-8"

    def test_login_page_has_no_cache(self, auth_server):
        _, headers, _ = _request(auth_server, "/_karta/login")
        assert headers["Cache-Control"] == "no-store"


class TestLoginFlow:
    def test_valid_login_sets_cookie_and_redirects(self, auth_server):
        body = urlencode({"username": "alice", "password": "secret"}).encode()
        status, headers, _ = _request(
            auth_server,
            "/_karta/login",
            method="POST",
            body=body,
            content_type="application/x-www-form-urlencoded",
        )
        assert status == 303
        assert headers["Location"] == "/"
        assert COOKIE_NAME in headers["Set-Cookie"]
        assert "HttpOnly" in headers["Set-Cookie"]
        assert "SameSite=Strict" in headers["Set-Cookie"]

    def test_invalid_login_shows_error(self, auth_server):
        body = urlencode({"username": "alice", "password": "wrong"}).encode()
        status, _, resp_body = _request(
            auth_server,
            "/_karta/login",
            method="POST",
            body=body,
            content_type="application/x-www-form-urlencoded",
        )
        assert status == 200
        assert b"Invalid username or password" in resp_body

    def test_oversized_login_body_returns_413(self, auth_server):
        status, _, _ = _request(
            auth_server,
            "/_karta/login",
            method="POST",
            body=b"x" * 8193,
            content_type="application/x-www-form-urlencoded",
        )
        assert status == 413

    def test_session_cookie_grants_access(self, auth_server):
        body = urlencode({"username": "alice", "password": "secret"}).encode()
        _, headers, _ = _request(
            auth_server,
            "/_karta/login",
            method="POST",
            body=body,
            content_type="application/x-www-form-urlencoded",
        )
        cookie = headers["Set-Cookie"].split(";")[0]
        status, _, resp_body = _request(auth_server, "/secret.txt", cookie=cookie)
        assert status == 200
        assert resp_body == b"top secret"

    def test_directory_listing_shows_logout(self, auth_server):
        body = urlencode({"username": "alice", "password": "secret"}).encode()
        _, headers, _ = _request(
            auth_server,
            "/_karta/login",
            method="POST",
            body=body,
            content_type="application/x-www-form-urlencoded",
        )
        cookie = headers["Set-Cookie"].split(";")[0]
        status, _, resp_body = _request(auth_server, "/", cookie=cookie)
        assert status == 200
        assert b"Sign out" in resp_body
        assert b"/_karta/logout" in resp_body


class TestLogout:
    def test_logout_clears_cookie_and_redirects(self, auth_server):
        body = urlencode({"username": "alice", "password": "secret"}).encode()
        _, headers, _ = _request(
            auth_server,
            "/_karta/login",
            method="POST",
            body=body,
            content_type="application/x-www-form-urlencoded",
        )
        cookie = headers["Set-Cookie"].split(";")[0]

        status, headers, _ = _request(auth_server, "/_karta/logout", cookie=cookie)
        assert status == 303
        assert headers["Location"] == "/_karta/login"
        assert "Max-Age=0" in headers["Set-Cookie"]

    def test_session_invalid_after_logout(self, auth_server):
        body = urlencode({"username": "alice", "password": "secret"}).encode()
        _, headers, _ = _request(
            auth_server,
            "/_karta/login",
            method="POST",
            body=body,
            content_type="application/x-www-form-urlencoded",
        )
        cookie = headers["Set-Cookie"].split(";")[0]

        _request(auth_server, "/_karta/logout", cookie=cookie)

        status, _, _ = _request(auth_server, "/secret.txt", cookie=cookie)
        assert status == 303

    def test_logout_without_cookie(self, auth_server):
        status, headers, _ = _request(auth_server, "/_karta/logout")
        assert status == 303
        assert headers["Location"] == "/_karta/login"


class TestCurlAuth:
    def test_basic_auth_header_grants_access(self, auth_server):
        status, _, body = _request(
            auth_server,
            "/secret.txt",
            auth=("alice", "secret"),
        )
        assert status == 200
        assert body == b"top secret"

    def test_bad_basic_auth_returns_401(self, auth_server):
        status, headers, _ = _request(
            auth_server,
            "/secret.txt",
            auth=("alice", "wrong"),
        )
        assert status == 401
        assert headers["WWW-Authenticate"] == 'Basic realm="karta"'

    def test_auth_required_for_static(self, auth_server):
        status, _, _ = _request(auth_server, "/_karta/static/karta.css")
        assert status == 303

    def test_auth_required_for_favicon(self, auth_server):
        status, _, _ = _request(auth_server, "/favicon.ico")
        assert status == 303


class TestPostRouting:
    def test_post_unauthenticated_redirects_to_login(self, auth_server):
        status, _, _ = _request(auth_server, "/some/path", method="POST")
        assert status == 303
