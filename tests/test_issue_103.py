"""Regression tests for issue #103 — defensive fixes in auth/origin/upload paths."""

import io
import threading
from functools import partial
from http.server import HTTPServer
from urllib.request import Request, urlopen

import pytest

from neev.auth import LoginRateLimiter, SessionStore
from neev.config import Config
from neev.server import NeevHandler
from neev.upload import UploadError, handle_upload


# -- Fixtures ----------------------------------------------------------------


def _make_config(serve_dir, **overrides):
    defaults = {
        "directory": serve_dir,
        "host": "127.0.0.1",
        "port": 0,
        "username": None,
        "password": None,
        "show_hidden": False,
        "enable_zip_download": True,
        "max_zip_size": 104857600,
        "enable_upload": True,
    }
    defaults.update(overrides)
    return Config(**defaults)


def _start_server(config):
    sessions = SessionStore()
    rate_limiter = LoginRateLimiter()
    handler = partial(NeevHandler, config, sessions, rate_limiter)
    httpd = HTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, f"http://127.0.0.1:{port}"


@pytest.fixture
def open_server(tmp_path):
    (tmp_path / "hello.txt").write_text("hello")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.txt").write_text("nested")
    config = _make_config(tmp_path)
    httpd, base = _start_server(config)
    yield base, tmp_path
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def server_ctx(tmp_path):
    (tmp_path / "hello.txt").write_text("hello")
    config = _make_config(tmp_path, username="alice", password="secret")
    sessions = SessionStore()
    rate_limiter = LoginRateLimiter()
    handler = partial(NeevHandler, config, sessions, rate_limiter)
    httpd = HTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}", tmp_path
    httpd.shutdown()
    httpd.server_close()


def _post(url, path, body=b"", headers=None, content_type="application/x-www-form-urlencoded"):
    req = Request(f"{url}{path}", data=body, method="POST")
    req.add_header("Content-Type", content_type)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        resp = urlopen(req)
        return resp.status, resp.read()
    except Exception as exc:
        if hasattr(exc, "code"):
            return exc.code, exc.read()
        raise


# -- Finding 1: malformed Referer should return 400, not 500 ------------------


class TestMalformedReferer:
    def test_about_blank_referer_returns_400(self, server_ctx):
        base, _ = server_ctx
        status, body = _post(base, "/?zip", b"items=hello.txt", headers={"Referer": "about:blank"})
        assert status == 400
        assert b"malformed" in body.lower() or b"bad request" in body.lower()

    def test_bare_referer_returns_400(self, server_ctx):
        base, _ = server_ctx
        status, _ = _post(base, "/?zip", b"items=hello.txt", headers={"Referer": "foo"})
        assert status == 400

    def test_empty_referer_returns_400(self, server_ctx):
        base, _ = server_ctx
        status, _ = _post(base, "/?zip", b"items=hello.txt", headers={"Referer": "//host/path"})
        assert status == 400


# -- Finding 2: login POST enforces origin check -----------------------------


class TestLoginCsrf:
    def test_cross_origin_login_post_rejected(self, server_ctx):
        base, _ = server_ctx
        status, body = _post(
            base,
            "/_neev/login",
            b"username=alice&password=secret",
            headers={"Origin": "http://evil.com"},
        )
        assert status == 403
        assert b"origin mismatch" in body

    def test_same_origin_login_post_allowed(self, server_ctx):
        base, _ = server_ctx
        host = base.replace("http://", "")
        status, _ = _post(
            base,
            "/_neev/login",
            b"username=alice&password=secret",
            headers={"Origin": f"http://{host}"},
        )
        # 303 redirect on success
        assert status in (200, 303)


# -- Finding 3: selective ZIP sanitizes item names ---------------------------


class TestSelectiveZipSanitization:
    def test_absolute_path_item_rejected(self, open_server):
        base, _ = open_server
        host = base.replace("http://", "")
        status, body = _post(
            base,
            "/?zip",
            b"items=/etc/passwd",
            headers={"Origin": f"http://{host}"},
        )
        assert status == 400
        assert b"invalid" in body.lower()

    def test_traversal_item_rejected(self, open_server):
        base, _ = open_server
        host = base.replace("http://", "")
        status, _ = _post(
            base,
            "/?zip",
            b"items=..",
            headers={"Origin": f"http://{host}"},
        )
        assert status == 400

    def test_nested_path_item_rejected(self, open_server):
        base, _ = open_server
        host = base.replace("http://", "")
        status, _ = _post(
            base,
            "/?zip",
            b"items=sub/nested.txt",
            headers={"Origin": f"http://{host}"},
        )
        assert status == 400


# -- Finding 4: upload rejects collisions ------------------------------------


def _build_multipart(filename: str, content: bytes, boundary: str = "bndry") -> bytes:
    return (
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        + content
        + f"\r\n--{boundary}--\r\n".encode()
    )


class TestUploadCollision:
    def test_upload_rejects_existing_file(self, tmp_path):
        existing = tmp_path / "dup.txt"
        existing.write_text("original")

        boundary = "bndry"
        body = _build_multipart("dup.txt", b"new content", boundary)

        with pytest.raises(UploadError, match="already exists"):
            handle_upload(
                rfile=io.BytesIO(body),
                content_type=f"multipart/form-data; boundary={boundary}",
                content_length=len(body),
                target_dir=tmp_path,
                base_dir=tmp_path,
            )

        assert existing.read_text() == "original"
