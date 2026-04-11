"""Integration tests for file preview functionality."""

import threading
from functools import partial
from http.server import HTTPServer
from urllib.request import Request, urlopen

import pytest

from neev.auth import LoginRateLimiter, SessionStore
from neev.config import Config
from neev.server import NeevHandler


# -- Test fixtures -----------------------------------------------------------


@pytest.fixture
def serve_dir(tmp_path):
    """Create a populated temp directory for serving."""
    (tmp_path / "hello.txt").write_text("hello world")
    (tmp_path / "page.html").write_text("<h1>Hi</h1>")
    (tmp_path / "data.json").write_text('{"key": "value"}')
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "nested.txt").write_text("nested content")
    return tmp_path


@pytest.fixture
def config(serve_dir):
    """Create a Config pointing at the temp directory."""
    return Config(
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


@pytest.fixture
def server(config):
    """Start a real HTTP server on a random port, yield base URL, shut down after."""
    sessions = SessionStore()
    handler = partial(NeevHandler, config, sessions, LoginRateLimiter())
    httpd = HTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()
    httpd.server_close()


def _get(url, path="/"):
    """Make a GET request and return (status, headers, body)."""
    req = Request(f"{url}{path}")
    try:
        resp = urlopen(req)
        return resp.status, dict(resp.headers), resp.read()
    except Exception as exc:
        if hasattr(exc, "code"):
            return exc.code, dict(exc.headers), exc.read()
        raise


# -- File preview ------------------------------------------------------------


class TestFilePreview:
    def test_image_preview(self, server):
        status, headers, body = _get(server, "/image.png?preview")
        assert status == 200
        assert headers["Content-Type"] == "text/html; charset=utf-8"
        assert b"<img" in body
        assert b"image.png" in body

    def test_text_preview(self, server):
        status, headers, body = _get(server, "/hello.txt?preview")
        assert status == 200
        assert headers["Content-Type"] == "text/html; charset=utf-8"
        assert b"code-content" in body
        assert b"hello.txt" in body

    def test_json_preview(self, server):
        status, _, body = _get(server, "/data.json?preview")
        assert status == 200
        assert b"code-content" in body

    def test_html_preview(self, server):
        status, _, body = _get(server, "/page.html?preview")
        assert status == 200
        assert b"page.html" in body

    def test_pdf_preview(self, server, serve_dir):
        (serve_dir / "doc.pdf").write_bytes(b"%PDF-1.4 fake")
        status, _, body = _get(server, "/doc.pdf?preview")
        assert status == 200
        assert b"<embed" in body

    def test_video_preview(self, server, serve_dir):
        (serve_dir / "clip.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
        status, _, body = _get(server, "/clip.mp4?preview")
        assert status == 200
        assert b"<video" in body

    def test_audio_preview(self, server, serve_dir):
        (serve_dir / "song.mp3").write_bytes(b"ID3fake")
        status, _, body = _get(server, "/song.mp3?preview")
        assert status == 200
        assert b"<audio" in body

    def test_preview_has_download_link(self, server):
        _, _, body = _get(server, "/image.png?preview")
        assert b"?download" in body

    def test_preview_has_back_link(self, server):
        _, _, body = _get(server, "/image.png?preview")
        assert b"Back to folder" in body

    def test_nonpreviewable_falls_through(self, server, serve_dir):
        (serve_dir / "data.bin").write_bytes(b"\x00\x01\x02")
        status, headers, _ = _get(server, "/data.bin?preview")
        # application/octet-stream is not previewable, serves as download
        assert status == 200
        assert "octet-stream" in headers["Content-Type"]
