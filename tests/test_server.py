import threading
from functools import partial
from http.server import HTTPServer
from unittest.mock import patch
from urllib.request import Request, urlopen

import pytest

from neev.auth import LoginRateLimiter, SessionStore
from neev.config import Config
from neev.server import NeevHandler, run_server


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


# -- File serving ------------------------------------------------------------


class TestFileServing:
    def test_serve_text_file(self, server):
        status, headers, body = _get(server, "/hello.txt")
        assert status == 200
        assert body == b"hello world"
        assert headers["Content-Type"] == "text/plain"
        assert headers["Content-Length"] == "11"

    def test_serve_html_file(self, server):
        status, headers, body = _get(server, "/page.html")
        assert status == 200
        assert body == b"<h1>Hi</h1>"
        assert headers["Content-Type"] == "text/html"

    def test_serve_json_file(self, server):
        status, headers, _ = _get(server, "/data.json")
        assert status == 200
        assert headers["Content-Type"] == "application/json"

    def test_serve_png_file(self, server):
        status, headers, _ = _get(server, "/image.png")
        assert status == 200
        assert headers["Content-Type"] == "image/png"

    def test_content_length_set(self, server):
        status, headers, _ = _get(server, "/hello.txt")
        assert status == 200
        assert headers["Content-Length"] == "11"

    def test_nested_file(self, server):
        status, _, body = _get(server, "/subdir/nested.txt")
        assert status == 200
        assert body == b"nested content"


# -- Directory listing -------------------------------------------------------


class TestDirectoryServing:
    def test_root_directory(self, server):
        status, headers, body = _get(server, "/")
        assert status == 200
        assert headers["Content-Type"] == "text/html; charset=utf-8"
        assert b"<!DOCTYPE html>" in body
        assert b"hello.txt" in body

    def test_subdirectory(self, server):
        status, headers, body = _get(server, "/subdir/")
        assert status == 200
        assert headers["Content-Type"] == "text/html; charset=utf-8"
        assert b"nested.txt" in body
        assert b".." in body

    def test_directory_hides_dotfiles(self, server, serve_dir):
        (serve_dir / ".hidden").write_text("secret")
        _, _, body = _get(server, "/")
        assert b".hidden" not in body

    def test_directory_lists_subdirs_first(self, server):
        _, _, body = _get(server, "/")
        body_str = body.decode()
        subdir_pos = body_str.find("subdir")
        hello_pos = body_str.find("hello.txt")
        assert subdir_pos < hello_pos


# -- Static assets -----------------------------------------------------------


class TestStaticAssets:
    def test_serve_css(self, server):
        status, headers, body = _get(server, "/_neev/static/neev.css")
        assert status == 200
        assert headers["Content-Type"] == "text/css; charset=utf-8"
        assert b"tailwindcss" in body

    def test_serve_js(self, server):
        status, headers, _ = _get(server, "/_neev/static/alpine.min.js")
        assert status == 200
        assert "javascript" in headers["Content-Type"]

    def test_cache_header(self, server):
        _, headers, _ = _get(server, "/_neev/static/neev.css")
        assert "max-age=86400" in headers["Cache-Control"]

    def test_404_nonexistent_static(self, server):
        status, _, _ = _get(server, "/_neev/static/nope.css")
        assert status == 404

    def test_404_directory_traversal(self, server):
        status, _, _ = _get(server, "/_neev/static/../server.py")
        assert status == 404


# -- Error responses ---------------------------------------------------------


class TestErrorResponses:
    def test_404_nonexistent(self, server):
        status, _, body = _get(server, "/nonexistent.txt")
        assert status == 404
        assert body == b"Not Found"

    def test_403_traversal_dot_dot(self, server):
        status, _, body = _get(server, "/../../etc/passwd")
        assert status == 403
        assert body == b"Forbidden"

    def test_403_traversal_many_levels(self, server):
        status, _, _ = _get(server, "/../../../../../etc/shadow")
        assert status == 403

    def test_403_traversal_url_encoded(self, server):
        # %2e%2e decodes to .. before the handler sees it; traversal guard fires
        status, _, _ = _get(server, "/%2e%2e/etc/passwd")
        assert status in (403, 404)

    def test_traversal_double_encoded(self, server):
        # %25 decodes to %, leaving %2e%2e as a literal string — not .. so no traversal,
        # but the path doesn't exist either
        status, _, _ = _get(server, "/%252e%252e/etc/passwd")
        assert status in (403, 404)

    def test_403_symlink_outside(self, server, serve_dir):
        outside = serve_dir.parent / "outside_secret.txt"
        outside.write_text("secret")
        try:
            link = serve_dir / "escape.txt"
            link.symlink_to(outside)
            status, _, _ = _get(server, "/escape.txt")
            assert status == 403
        finally:
            outside.unlink()


# -- Request logging ---------------------------------------------------------


class TestRequestLogging:
    def test_log_request_outputs_to_stderr(self, server, capsys):
        _get(server, "/hello.txt")
        err = capsys.readouterr().err
        assert "GET" in err
        assert "/hello.txt" in err
        assert "200" in err

    def test_log_request_404_in_stderr(self, server, capsys):
        _get(server, "/missing.txt")
        err = capsys.readouterr().err
        assert "404" in err

    def test_log_request_non_digit_code(self):
        with patch("sys.stderr.isatty", return_value=False):
            handler = NeevHandler.__new__(NeevHandler)
            handler.command = "GET"
            handler.path = "/test"
            handler.log_request("-")

    def test_log_message_suppressed(self):
        handler = NeevHandler.__new__(NeevHandler)
        handler.log_message("test %s", "arg")


# -- Favicon -----------------------------------------------------------------


class TestFavicon:
    def test_favicon_returns_svg(self, server):
        status, headers, body = _get(server, "/favicon.svg")
        assert status == 200
        assert headers["Content-Type"] == "image/svg+xml"
        assert b"<svg" in body

    def test_favicon_has_cache_header(self, server):
        _, headers, _ = _get(server, "/favicon.svg")
        assert "max-age=86400" in headers["Cache-Control"]

    def test_favicon_not_logged(self, server, capsys):
        _get(server, "/favicon.svg")
        err = capsys.readouterr().err
        assert "favicon" not in err


# -- run_server --------------------------------------------------------------


class TestRunServer:
    def test_keyboard_interrupt_shuts_down(self, config):
        with patch.object(HTTPServer, "serve_forever", side_effect=KeyboardInterrupt):
            run_server(config)

    def test_server_close_called(self, config):
        with (
            patch.object(HTTPServer, "serve_forever", side_effect=KeyboardInterrupt),
            patch.object(HTTPServer, "server_close") as mock_close,
        ):
            run_server(config)
        mock_close.assert_called_once()


# -- Query parameter matching (regression for #105) --------------------------


@pytest.fixture
def zip_enabled_server(serve_dir):
    """Server with ZIP downloads enabled for testing ?zip query variants."""
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
    sessions = SessionStore()
    handler = partial(NeevHandler, cfg, sessions, LoginRateLimiter())
    httpd = HTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()
    httpd.server_close()


class TestQueryParamMatching:
    """Before the fix, `parsed.query == 'zip'` required exact equality, so
    adding cache-busting or unrelated params silently broke the feature."""

    def test_zip_with_extra_param(self, zip_enabled_server):
        status, headers, _ = _get(zip_enabled_server, "/subdir?zip&cachebust=1")
        assert status == 200
        assert "application/zip" in headers["Content-Type"]

    def test_preview_markdown_with_extra_param(self, serve_dir, server):
        (serve_dir / "doc.md").write_text("# Title\n\nBody")
        status, headers, _ = _get(server, "/doc.md?preview&t=123")
        assert status == 200
        assert "text/html" in headers["Content-Type"]

    def test_preview_image_with_extra_param(self, server):
        """Generic preview wraps the file in an HTML viewer page."""
        status, headers, _ = _get(server, "/image.png?preview&v=2")
        assert status == 200
        assert "text/html" in headers["Content-Type"]

    def test_download_with_extra_param(self, server):
        status, headers, _ = _get(server, "/hello.txt?download&bust=1")
        assert status == 200
        assert "attachment" in headers.get("Content-Disposition", "")
