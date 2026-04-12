"""Query parameter matching regression tests (originally from test_server.py)."""

import threading
from functools import partial
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

import pytest

from neev.auth import LoginRateLimiter, SessionStore
from neev.config import Config
from neev.server import NeevHandler


@pytest.fixture
def serve_dir(tmp_path):
    (tmp_path / "hello.txt").write_text("hello world")
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "nested.txt").write_text("nested content")
    return tmp_path


def _make_server(cfg):
    sessions = SessionStore()
    handler = partial(NeevHandler, cfg, sessions, LoginRateLimiter())
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, f"http://127.0.0.1:{port}"


@pytest.fixture
def zip_server(serve_dir):
    cfg = Config(
        directory=serve_dir,
        host="127.0.0.1",
        port=0,
        username=None,
        password=None,
        show_hidden=False,
        enable_zip_download=True,
        max_zip_size=104857600,
        enable_upload=False,
    )
    httpd, url = _make_server(cfg)
    yield url
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def plain_server(serve_dir):
    cfg = Config(
        directory=serve_dir,
        host="127.0.0.1",
        port=0,
        username=None,
        password=None,
        show_hidden=False,
        enable_zip_download=False,
        max_zip_size=104857600,
        enable_upload=False,
    )
    httpd, url = _make_server(cfg)
    yield url
    httpd.shutdown()
    httpd.server_close()


def _get(url, path="/"):
    req = Request(f"{url}{path}")
    resp = urlopen(req)
    return resp.status, dict(resp.headers), resp.read()


class TestQueryParamMatching:
    """Before the fix, `parsed.query == 'zip'` required exact equality, so
    adding cache-busting or unrelated params silently broke the feature."""

    def test_zip_with_extra_param(self, zip_server):
        status, headers, _ = _get(zip_server, "/subdir?zip&cachebust=1")
        assert status == 200
        assert "application/zip" in headers["Content-Type"]

    def test_preview_markdown_with_extra_param(self, serve_dir, plain_server):
        (serve_dir / "doc.md").write_text("# Title\n\nBody")
        status, headers, _ = _get(plain_server, "/doc.md?preview&t=123")
        assert status == 200
        assert "text/html" in headers["Content-Type"]

    def test_preview_image_with_extra_param(self, plain_server):
        status, headers, _ = _get(plain_server, "/image.png?preview&v=2")
        assert status == 200
        assert "text/html" in headers["Content-Type"]

    def test_download_with_extra_param(self, plain_server):
        status, headers, _ = _get(plain_server, "/hello.txt?download&bust=1")
        assert status == 200
        assert "attachment" in headers.get("Content-Disposition", "")
