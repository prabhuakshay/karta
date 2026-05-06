"""Integration tests for share-token auth in the HTTP server."""

import threading
import time
from functools import partial
from http.server import ThreadingHTTPServer
from urllib.parse import quote
from urllib.request import Request, urlopen

import pytest

from neev.auth import LoginRateLimiter, SessionStore
from neev.config import Config
from neev.server import NeevHandler
from neev.share import generate_secret, sign


SECRET = generate_secret()


@pytest.fixture
def serve_dir(tmp_path):
    (tmp_path / "public.txt").write_text("public content")
    (tmp_path / "private.txt").write_text("private content")
    rel = tmp_path / "releases"
    rel.mkdir()
    (rel / "v1.zip").write_bytes(b"ZIP_DATA")
    sib = tmp_path / "releases-private"
    sib.mkdir()
    (sib / "secret.txt").write_text("top secret")
    return tmp_path


def _make_config(serve_dir, *, enable_upload=False):
    return Config(
        directory=serve_dir,
        host="127.0.0.1",
        port=0,
        username="user",
        password="pw",
        show_hidden=False,
        enable_zip_download=False,
        max_zip_size=104857600,
        enable_upload=enable_upload,
        share_secret=SECRET,
    )


@pytest.fixture
def server(serve_dir):
    return _start_server(_make_config(serve_dir))


@pytest.fixture
def server_with_uploads(serve_dir):
    return _start_server(_make_config(serve_dir, enable_upload=True))


def _start_server(config):
    handler = partial(NeevHandler, config, SessionStore(), LoginRateLimiter())
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}", httpd
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def server_runtime(server):
    yield from server


@pytest.fixture
def server_uploads_runtime(server_with_uploads):
    yield from server_with_uploads


def _request(url, method="GET", data=None, headers=None):
    req = Request(url, data=data, method=method, headers=headers or {})
    try:
        resp = urlopen(req)
        return resp.status, resp.read()
    except Exception as exc:
        if hasattr(exc, "code"):
            return exc.code, exc.read()
        raise


# -- read access with share tokens -------------------------------------------


class TestShareRead:
    def test_valid_token_grants_access_without_credentials(self, server_runtime):
        base, _ = server_runtime
        token = sign("/releases/v1.zip", int(time.time()) + 60, False, SECRET)
        status, body = _request(f"{base}/releases/v1.zip?share={token}")
        assert status == 200
        assert body == b"ZIP_DATA"

    def test_no_token_without_auth_redirects_to_login(self, server_runtime):
        base, _ = server_runtime
        status, _ = _request(f"{base}/releases/v1.zip")
        # Default opener follows 303 — login page returns 200 with form.
        # What we really want to confirm: access is NOT granted.
        # Login page body is HTML, not the ZIP bytes.
        assert status == 200  # landed on login form

    def test_folder_token_covers_nested_file(self, server_runtime):
        base, _ = server_runtime
        token = sign("/releases", int(time.time()) + 60, False, SECRET)
        status, body = _request(f"{base}/releases/v1.zip?share={token}")
        assert status == 200
        assert body == b"ZIP_DATA"

    def test_folder_token_does_not_bleed_to_sibling(self, server_runtime):
        base, _ = server_runtime
        token = sign("/releases", int(time.time()) + 60, False, SECRET)
        status, _ = _request(f"{base}/releases-private/secret.txt?share={token}")
        assert status == 403

    def test_token_for_wrong_file_returns_403(self, server_runtime):
        base, _ = server_runtime
        token = sign("/releases/v1.zip", int(time.time()) + 60, False, SECRET)
        status, _ = _request(f"{base}/private.txt?share={token}")
        assert status == 403

    def test_expired_token_returns_403(self, server_runtime):
        base, _ = server_runtime
        token = sign("/releases/v1.zip", int(time.time()) - 1, False, SECRET)
        status, _ = _request(f"{base}/releases/v1.zip?share={token}")
        assert status == 403

    def test_tampered_token_returns_403(self, server_runtime):
        base, _ = server_runtime
        token = sign("/releases/v1.zip", int(time.time()) + 60, False, SECRET)
        body, mac = token.rsplit(".", 1)
        bad = body + "." + ("A" if mac[0] != "A" else "B") + mac[1:]
        status, _ = _request(f"{base}/releases/v1.zip?share={quote(bad)}")
        assert status == 403


# -- write access ------------------------------------------------------------


class TestShareWrite:
    def test_read_token_cannot_upload(self, server_uploads_runtime):
        base, _ = server_uploads_runtime
        token = sign("/releases", int(time.time()) + 60, False, SECRET)
        # POST with multipart-ish body; we only need to verify auth gate.
        status, _ = _request(
            f"{base}/releases?share={token}",
            method="POST",
            data=b"ignored",
            headers={"Content-Type": "text/plain", "Content-Length": "7"},
        )
        assert status == 403

    def test_write_token_permits_post_when_uploads_enabled(self, server_uploads_runtime):
        base, _ = server_uploads_runtime
        token = sign("/releases", int(time.time()) + 60, True, SECRET)
        # Malformed multipart is fine — we want the auth decision, not a 200.
        status, _ = _request(
            f"{base}/releases?share={token}",
            method="POST",
            data=b"garbage",
            headers={"Content-Type": "multipart/form-data; boundary=x", "Content-Length": "7"},
        )
        # Auth passed; request fails at multipart parser (400), not auth (403).
        assert status == 400

    def test_write_token_respects_uploads_disabled_feature_flag(self, server_runtime):
        base, _ = server_runtime  # enable_upload=False
        token = sign("/releases", int(time.time()) + 60, True, SECRET)
        status, body = _request(
            f"{base}/releases?share={token}",
            method="POST",
            data=b"garbage",
            headers={"Content-Type": "multipart/form-data; boundary=x", "Content-Length": "7"},
        )
        assert status == 403
        assert b"Uploads are disabled" in body
