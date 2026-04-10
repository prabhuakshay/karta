"""Tests for karta.auth — Basic Auth credential validation."""

import base64
import threading
from functools import partial
from http.server import HTTPServer
from urllib.request import Request, urlopen

import pytest

from karta.auth import check_basic_auth
from karta.config import Config
from karta.server import KartaHandler


# -- Unit tests for check_basic_auth -----------------------------------------


def _encode_creds(username: str, password: str) -> str:
    """Build a valid Basic Auth header value."""
    raw = f"{username}:{password}".encode()
    return f"Basic {base64.b64encode(raw).decode()}"


class TestCheckBasicAuth:
    def test_valid_credentials(self):
        header = _encode_creds("alice", "secret")
        assert check_basic_auth(header, "alice", "secret") is True

    def test_wrong_username(self):
        header = _encode_creds("bob", "secret")
        assert check_basic_auth(header, "alice", "secret") is False

    def test_wrong_password(self):
        header = _encode_creds("alice", "wrong")
        assert check_basic_auth(header, "alice", "secret") is False

    def test_none_header(self):
        assert check_basic_auth(None, "alice", "secret") is False

    def test_empty_header(self):
        assert check_basic_auth("", "alice", "secret") is False

    def test_missing_basic_prefix(self):
        header = "Bearer some-token"
        assert check_basic_auth(header, "alice", "secret") is False

    def test_malformed_base64(self):
        header = "Basic !!!not-valid-base64!!!"
        assert check_basic_auth(header, "alice", "secret") is False

    def test_no_colon_in_decoded(self):
        encoded = base64.b64encode(b"nocolonhere").decode()
        header = f"Basic {encoded}"
        assert check_basic_auth(header, "alice", "secret") is False

    def test_empty_username_and_password(self):
        header = _encode_creds("", "")
        assert check_basic_auth(header, "", "") is True

    def test_password_with_colon(self):
        header = _encode_creds("alice", "pass:word:extra")
        assert check_basic_auth(header, "alice", "pass:word:extra") is True

    def test_unicode_credentials(self):
        header = _encode_creds("ålice", "sëcret")
        assert check_basic_auth(header, "ålice", "sëcret") is True


# -- Integration tests: auth wired into the server ---------------------------


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
        enable_upload=False,
    )


@pytest.fixture
def auth_server(auth_config):
    """Start a server with auth enabled, yield base URL."""
    handler = partial(KartaHandler, auth_config)
    httpd = HTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()
    httpd.server_close()


def _get(url, path="/", auth: tuple[str, str] | None = None):
    """Make a GET request, optionally with Basic Auth credentials."""
    req = Request(f"{url}{path}")
    if auth:
        creds = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        req.add_header("Authorization", f"Basic {creds}")
    try:
        resp = urlopen(req)
        return resp.status, dict(resp.headers), resp.read()
    except Exception as exc:
        if hasattr(exc, "code"):
            return exc.code, dict(exc.headers), exc.read()
        raise


class TestAuthIntegration:
    def test_no_credentials_returns_401(self, auth_server):
        status, headers, _ = _get(auth_server, "/")
        assert status == 401
        assert headers["WWW-Authenticate"] == 'Basic realm="karta"'

    def test_wrong_credentials_returns_401(self, auth_server):
        status, headers, _ = _get(auth_server, "/", auth=("bob", "wrong"))
        assert status == 401
        assert headers["WWW-Authenticate"] == 'Basic realm="karta"'

    def test_correct_credentials_grant_access(self, auth_server):
        status, _, body = _get(auth_server, "/secret.txt", auth=("alice", "secret"))
        assert status == 200
        assert body == b"top secret"

    def test_auth_required_for_directory(self, auth_server):
        status, _, _ = _get(auth_server, "/")
        assert status == 401

    def test_auth_required_for_favicon(self, auth_server):
        status, _, _ = _get(auth_server, "/favicon.ico")
        assert status == 401

    def test_auth_required_for_static(self, auth_server):
        status, _, _ = _get(auth_server, "/_karta/static/karta.css")
        assert status == 401

    def test_401_body_is_html(self, auth_server):
        _, headers, body = _get(auth_server, "/")
        assert headers["Content-Type"] == "text/html; charset=utf-8"
        assert b"401" in body

    def test_malformed_auth_header_returns_401(self, auth_server):
        req = Request(f"{auth_server}/")
        req.add_header("Authorization", "Basic !!!bad!!!")
        try:
            resp = urlopen(req)
            status = resp.status
        except Exception as exc:
            status = exc.code
        assert status == 401
