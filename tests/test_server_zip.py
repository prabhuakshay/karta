"""Integration tests for ZIP download functionality."""

import http.client
import threading
import zipfile
from functools import partial
from http.server import HTTPServer
from io import BytesIO
from urllib.parse import quote
from urllib.request import Request, urlopen

import pytest

from neev.auth import SessionStore
from neev.config import Config
from neev.server import NeevHandler


# -- Test fixtures -----------------------------------------------------------


@pytest.fixture
def serve_dir(tmp_path):
    """Create a populated temp directory for serving."""
    (tmp_path / "hello.txt").write_text("hello world")
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "nested.txt").write_text("nested content")
    return tmp_path


@pytest.fixture
def zip_config(serve_dir):
    """Create a Config with ZIP downloads enabled."""
    return Config(
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


@pytest.fixture
def zip_server(zip_config):
    """Start a server with ZIP downloads enabled."""
    sessions = SessionStore()
    handler = partial(NeevHandler, zip_config, sessions)
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
            return exc.code, dict(exc.headers), exc.read()  # type: ignore[attr-defined]
        raise


def _post(url, path="/", body=b"", content_type="application/x-www-form-urlencoded"):
    """Make a POST request and return (status, headers, body)."""
    req = Request(f"{url}{path}", data=body, method="POST")
    req.add_header("Content-Type", content_type)
    try:
        resp = urlopen(req)
        return resp.status, dict(resp.headers), resp.read()
    except Exception as exc:
        if hasattr(exc, "code"):
            return exc.code, dict(exc.headers), exc.read()  # type: ignore[attr-defined]
        raise


def _zip_server_for(config: Config):
    """Start a ZIP-enabled server for the given config; return (httpd, base_url)."""
    sessions = SessionStore()
    handler = partial(NeevHandler, config, sessions)
    httpd = HTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, f"http://127.0.0.1:{port}"


# -- ZIP download tests -------------------------------------------------------


class TestZipDownload:
    def test_zip_disabled_returns_403(self, serve_dir):
        """ZIP endpoint returns 403 when the feature is disabled."""
        no_zip_config = Config(
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
        httpd, base = _zip_server_for(no_zip_config)
        try:
            status, _, body = _get(base, "/?zip")
            assert status == 403
            assert b"disabled" in body
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_zip_enabled_returns_zip(self, zip_server):
        status, headers, _ = _get(zip_server, "/?zip")
        assert status == 200
        assert headers["Content-Type"] == "application/zip"
        assert "attachment" in headers["Content-Disposition"]

    def test_zip_filename_matches_directory(self, zip_server):
        status, headers, _ = _get(zip_server, "/subdir/?zip")
        assert status == 200
        assert 'filename="subdir.zip"' in headers["Content-Disposition"]

    def test_zip_content_is_valid(self, zip_server):
        _, _, body = _get(zip_server, "/subdir/?zip")
        zf = zipfile.ZipFile(BytesIO(body))
        assert zf.testzip() is None
        assert "nested.txt" in zf.namelist()

    def test_zip_too_large_returns_413(self, serve_dir):
        """A tiny max_zip_size triggers a 413 response."""
        tiny_config = Config(
            directory=serve_dir,
            host="127.0.0.1",
            port=0,
            username=None,
            password=None,
            show_hidden=False,
            enable_zip_download=True,
            max_zip_size=1,
            enable_upload=False,
        )
        httpd, base = _zip_server_for(tiny_config)
        try:
            status, _, body = _get(base, "/?zip")
            assert status == 413
            assert b"too large" in body
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_zip_nonexistent_dir_returns_404(self, zip_server):
        status, _, _ = _get(zip_server, "/nope/?zip")
        assert status == 404

    def test_zip_filename_sanitizes_quotes(self, serve_dir, zip_config):
        """Directory name with quotes must not produce a broken Content-Disposition header."""
        bad_name = 'evil"; filename="injected'
        (serve_dir / bad_name).mkdir()
        httpd, base = _zip_server_for(zip_config)
        try:
            status, headers, _ = _get(base, f"/{quote(bad_name, safe='')}/?zip")
            assert status == 200
            # The filename value between the outer quotes must contain no literal quotes
            filename_value = headers["Content-Disposition"].split('filename="', 1)[1].rstrip('"')
            assert '"' not in filename_value
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_zip_filename_sanitizes_newlines(self, serve_dir, zip_config):
        """Directory name with newlines must not enable HTTP header injection."""
        bad_name = "inject\nExtra-Header"
        (serve_dir / bad_name).mkdir()
        httpd, base = _zip_server_for(zip_config)
        try:
            status, headers, _ = _get(base, f"/{quote(bad_name, safe='')}/?zip")
            assert status == 200
            disposition = headers["Content-Disposition"]
            assert "\n" not in disposition
            assert "\r" not in disposition
        finally:
            httpd.shutdown()
            httpd.server_close()


class TestSelectiveZipDownload:
    def test_selective_zip_single_file(self, zip_server):
        status, headers, body = _post(zip_server, "/?zip", b"items=hello.txt")
        assert status == 200
        assert headers["Content-Type"] == "application/zip"
        zf = zipfile.ZipFile(BytesIO(body))
        assert "hello.txt" in zf.namelist()

    def test_selective_zip_directory(self, zip_server):
        status, _, body = _post(zip_server, "/?zip", b"items=subdir")
        assert status == 200
        zf = zipfile.ZipFile(BytesIO(body))
        names = zf.namelist()
        assert any("nested.txt" in n for n in names)

    def test_selective_zip_multiple_items(self, zip_server):
        status, _, body = _post(zip_server, "/?zip", b"items=hello.txt&items=subdir")
        assert status == 200
        zf = zipfile.ZipFile(BytesIO(body))
        names = zf.namelist()
        assert "hello.txt" in names
        assert any("nested.txt" in n for n in names)

    def test_selective_zip_disabled_returns_403(self, serve_dir):
        no_zip_config = Config(
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
        httpd, base = _zip_server_for(no_zip_config)
        try:
            status, _, body = _post(base, "/?zip", b"items=hello.txt")
            assert status == 403
            assert b"disabled" in body
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_selective_zip_empty_items_returns_400(self, zip_server):
        status, _, _body = _post(zip_server, "/?zip", b"")
        assert status == 400

    def test_selective_zip_no_items_param_returns_400(self, zip_server):
        status, _, _body = _post(zip_server, "/?zip", b"other=value")
        assert status == 400

    def test_selective_zip_invalid_item_skipped(self, zip_server):
        status, _, body = _post(zip_server, "/?zip", b"items=hello.txt&items=nonexistent.txt")
        assert status == 200
        zf = zipfile.ZipFile(BytesIO(body))
        assert "hello.txt" in zf.namelist()
        assert "nonexistent.txt" not in zf.namelist()

    def test_selective_zip_filename_has_selected_suffix(self, zip_server):
        _, headers, _ = _post(zip_server, "/?zip", b"items=hello.txt")
        assert "selected.zip" in headers["Content-Disposition"]

    def test_selective_zip_malformed_content_length_returns_400(self, zip_server):
        host, port = zip_server.replace("http://", "").split(":")
        conn = http.client.HTTPConnection(host, int(port))
        conn.request(
            "POST",
            "/?zip",
            headers={"Content-Length": "abc", "Content-Type": "application/x-www-form-urlencoded"},
        )
        resp = conn.getresponse()
        assert resp.status == 400
        assert b"Invalid Content-Length" in resp.read()
        conn.close()

    def test_selective_zip_too_large_returns_413(self, serve_dir):
        tiny_config = Config(
            directory=serve_dir,
            host="127.0.0.1",
            port=0,
            username=None,
            password=None,
            show_hidden=False,
            enable_zip_download=True,
            max_zip_size=1,
            enable_upload=False,
        )
        httpd, base = _zip_server_for(tiny_config)
        try:
            status, _, body = _post(base, "/?zip", b"items=hello.txt")
            assert status == 413
            assert b"too large" in body
        finally:
            httpd.shutdown()
            httpd.server_close()
