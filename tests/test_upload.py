"""Integration tests for file upload and folder creation via HTTP."""

import http.client
import threading
from functools import partial
from http.server import HTTPServer
from urllib.request import Request, urlopen

import pytest

from neev.auth import LoginRateLimiter, SessionStore
from neev.config import Config
from neev.server import NeevHandler
from neev.upload import MAX_UPLOAD_SIZE


# -- Fixtures -----------------------------------------------------------------


@pytest.fixture
def serve_dir(tmp_path):
    """Create a temp directory for upload tests."""
    (tmp_path / "existing.txt").write_text("already here")
    sub = tmp_path / "subdir"
    sub.mkdir()
    return tmp_path


def _make_config(serve_dir, enable_upload):
    return Config(
        directory=serve_dir,
        host="127.0.0.1",
        port=0,
        username=None,
        password=None,
        show_hidden=False,
        enable_zip_download=False,
        max_zip_size=104857600,
        enable_upload=enable_upload,
    )


def _start_server(config):
    sessions = SessionStore()
    handler = partial(NeevHandler, config, sessions, LoginRateLimiter())
    httpd = HTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, f"http://127.0.0.1:{port}"


@pytest.fixture
def upload_server(serve_dir):
    """Start a server with uploads enabled."""
    httpd, url = _start_server(_make_config(serve_dir, enable_upload=True))
    yield url
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def no_upload_server(serve_dir):
    """Start a server with uploads disabled."""
    httpd, url = _start_server(_make_config(serve_dir, enable_upload=False))
    yield url
    httpd.shutdown()
    httpd.server_close()


# -- Helpers ------------------------------------------------------------------


def _build_multipart(files, boundary="testboundary"):
    """Build a multipart/form-data body from a list of (field, filename, data)."""
    parts = []
    for field, filename, data in files:
        part = f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"'
        if filename:
            part += f'; filename="{filename}"'
        part += "\r\n\r\n"
        parts.append(part.encode() + data + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _post(url, path, body=b"", content_type="", headers=None):
    """Make a POST request and return (status, headers, body)."""
    req = Request(f"{url}{path}", data=body, method="POST")
    if content_type:
        req.add_header("Content-Type", content_type)
    for key, val in (headers or {}).items():
        req.add_header(key, val)
    try:
        resp = urlopen(req)
        return resp.status, dict(resp.headers), resp.read()
    except Exception as exc:
        if hasattr(exc, "code"):
            return exc.code, dict(exc.headers), exc.read()
        raise


# -- Upload server tests ------------------------------------------------------


class TestUploadServer:
    def test_upload_file_via_post(self, upload_server, serve_dir):
        body, ct = _build_multipart([("file", "uploaded.txt", b"via http")])
        status, _, _ = _post(upload_server, "/", body, ct)
        assert status == 200
        assert (serve_dir / "uploaded.txt").read_bytes() == b"via http"

    def test_upload_to_subdirectory(self, upload_server, serve_dir):
        body, ct = _build_multipart([("file", "sub.txt", b"in sub")])
        status, _, _ = _post(upload_server, "/subdir/", body, ct)
        assert status == 200
        assert (serve_dir / "subdir" / "sub.txt").read_bytes() == b"in sub"

    def test_upload_disabled_returns_403(self, no_upload_server):
        body, ct = _build_multipart([("file", "test.txt", b"data")])
        status, _, resp_body = _post(no_upload_server, "/", body, ct)
        assert status == 403
        assert b"disabled" in resp_body

    def test_upload_form_shown_when_enabled(self, upload_server):
        body = urlopen(Request(f"{upload_server}/")).read()
        assert b"multipart/form-data" in body

    def test_upload_form_hidden_when_disabled(self, no_upload_server):
        body = urlopen(Request(f"{no_upload_server}/")).read()
        assert b"multipart/form-data" not in body

    def test_upload_bad_content_type(self, upload_server):
        assert _post(upload_server, "/", b"not multipart", "text/plain")[0] == 400

    def test_upload_to_nonexistent_dir_returns_400(self, upload_server):
        body, ct = _build_multipart([("file", "f.txt", b"x")])
        assert _post(upload_server, "/nope/", body, ct)[0] == 400

    def test_upload_missing_content_length(self, upload_server):
        host, port = upload_server.replace("http://", "").split(":")
        conn = http.client.HTTPConnection(host, int(port))
        conn.request("POST", "/", headers={"Transfer-Encoding": "chunked"})
        resp = conn.getresponse()
        assert resp.status == 400
        assert b"Content-Length" in resp.read()
        conn.close()

    def test_upload_malformed_content_length_returns_400(self, upload_server):
        host, port = upload_server.replace("http://", "").split(":")
        conn = http.client.HTTPConnection(host, int(port))
        conn.request("POST", "/", headers={"Content-Length": "abc"})
        resp = conn.getresponse()
        assert resp.status == 400
        assert b"Invalid Content-Length" in resp.read()
        conn.close()

    def test_upload_too_large_returns_413(self, upload_server):
        body, ct = _build_multipart([("file", "big.txt", b"x" * 1024)])
        status, _, _ = _post(
            upload_server,
            "/",
            body,
            ct,
            headers={"Content-Length": str(MAX_UPLOAD_SIZE + 1)},
        )
        assert status == 413


# -- Mkdir server tests -------------------------------------------------------


class TestMkdirServer:
    def test_create_folder_via_post(self, upload_server, serve_dir):
        status, _, _ = _post(upload_server, "/?mkdir=testfolder")
        assert status == 200
        assert (serve_dir / "testfolder").is_dir()

    def test_create_folder_disabled_returns_403(self, no_upload_server):
        status, _, body = _post(no_upload_server, "/?mkdir=testfolder")
        assert status == 403
        assert b"disabled" in body

    def test_create_folder_existing_returns_400(self, upload_server):
        assert _post(upload_server, "/?mkdir=subdir")[0] == 400

    def test_create_folder_bad_target_returns_400(self, upload_server):
        assert _post(upload_server, "/nope/?mkdir=test")[0] == 400
