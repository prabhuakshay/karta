"""Tests that fill remaining coverage gaps across modules."""

import base64
import threading
import zipfile
from functools import partial
from http.server import HTTPServer
from unittest.mock import patch
from urllib.request import Request, urlopen

import pytest

from neev.auth import LoginRateLimiter, SessionStore
from neev.config import Config
from neev.html_markdown import render_markdown_preview
from neev.server import NeevHandler
from neev.zip import create_selective_zip_stream


# -- Fixtures ----------------------------------------------------------------


@pytest.fixture
def serve_dir(tmp_path):
    (tmp_path / "hello.txt").write_text("hello world")
    (tmp_path / "readme.md").write_text("# Title\n\nhello")
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "nested.txt").write_text("nested")
    return tmp_path


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
        "enable_upload": False,
    }
    defaults.update(overrides)
    return Config(**defaults)


@pytest.fixture
def server_ctx(serve_dir):
    """Start a server and return (httpd, base_url, config, rate_limiter)."""
    config = _make_config(serve_dir)
    sessions = SessionStore()
    rate_limiter = LoginRateLimiter()
    handler = partial(NeevHandler, config, sessions, rate_limiter)
    httpd = HTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd, f"http://127.0.0.1:{port}", config, rate_limiter
    httpd.shutdown()
    httpd.server_close()


def _post(url, path="/", body=b"", headers=None):
    req = Request(f"{url}{path}", data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        resp = urlopen(req)
        return resp.status, dict(resp.headers), resp.read()
    except Exception as exc:
        if hasattr(exc, "code"):
            return exc.code, dict(exc.headers), exc.read()
        raise


def _get(url, path="/"):
    req = Request(f"{url}{path}")
    try:
        resp = urlopen(req)
        return resp.status, dict(resp.headers), resp.read()
    except Exception as exc:
        if hasattr(exc, "code"):
            return exc.code, dict(exc.headers), exc.read()
        raise


# -- render_markdown_preview (html_markdown.py) ------------------------------


class TestRenderMarkdownPreview:
    def test_returns_complete_html(self):
        page = render_markdown_preview(
            filename="readme.md",
            raw_url="/readme.md?download",
            raw_url_js='"/readme.md?download"',
            parent_url="/",
        )
        assert "<!DOCTYPE html>" in page
        assert "readme.md" in page
        assert "/readme.md?download" in page

    def test_includes_css_and_js(self):
        page = render_markdown_preview("x.md", "/x.md", '"/x.md"', "/")
        assert "marked" in page


# -- Markdown preview via server (server_preview.py:40-51, server.py:187-188)


class TestMarkdownPreviewIntegration:
    def test_markdown_preview(self, server_ctx):
        _, base, _, _ = server_ctx
        status, headers, body = _get(base, "/readme.md?preview")
        assert status == 200
        assert headers["Content-Type"] == "text/html; charset=utf-8"
        assert b"readme.md" in body
        assert b"marked" in body


# -- CSRF origin check (server.py:115-128, 208) ------------------------------


class TestOriginCheck:
    def test_same_origin_allowed(self, server_ctx):
        _, base, _, _ = server_ctx
        host = base.replace("http://", "")
        status, _, _ = _post(
            base, "/?zip", b"items=hello.txt", headers={"Origin": f"http://{host}"}
        )
        assert status == 200

    def test_cross_origin_rejected(self, server_ctx):
        _, base, _, _ = server_ctx
        status, _, body = _post(
            base, "/?zip", b"items=hello.txt", headers={"Origin": "http://evil.com"}
        )
        assert status == 403
        assert b"origin mismatch" in body

    def test_referer_used_when_origin_missing(self, server_ctx):
        _, base, _, _ = server_ctx
        host = base.replace("http://", "")
        status, _, _ = _post(
            base,
            "/?zip",
            b"items=hello.txt",
            headers={"Referer": f"http://{host}/some/path"},
        )
        assert status == 200

    def test_cross_origin_referer_rejected(self, server_ctx):
        _, base, _, _ = server_ctx
        status, _, _ = _post(
            base, "/?zip", b"items=hello.txt", headers={"Referer": "http://evil.com/foo"}
        )
        assert status == 403


# -- 401 Unauthorized for API clients (server.py:_send_401) ------------------


class TestSend401:
    def test_401_sent_when_authorization_header_invalid(self, tmp_path):
        config = _make_config(tmp_path, username="alice", password="secret")
        sessions = SessionStore()
        rate_limiter = LoginRateLimiter()
        handler = partial(NeevHandler, config, sessions, rate_limiter)
        httpd = HTTPServer(("127.0.0.1", 0), handler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{port}"
            req = Request(f"{base}/")
            req.add_header("Authorization", "Basic YWxpY2U6d3Jvbmc=")
            try:
                urlopen(req)
                code, headers = None, {}
            except Exception as exc:
                code = getattr(exc, "code", None)
                headers = dict(getattr(exc, "headers", {}) or {})
            assert code == 401
            assert headers["WWW-Authenticate"].startswith("Basic")
        finally:
            httpd.shutdown()
            httpd.server_close()


# -- Cache-Control: no-store header (server.py:258-259) ----------------------


class TestCacheHeaderWithAuth:
    def test_no_store_header_set_with_auth(self, serve_dir):
        """Auth-enabled responses must set Cache-Control: no-store."""

        config = _make_config(serve_dir, username="alice", password="secret")
        sessions = SessionStore()
        rate_limiter = LoginRateLimiter()
        handler = partial(NeevHandler, config, sessions, rate_limiter)
        httpd = HTTPServer(("127.0.0.1", 0), handler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{port}"
            creds = base64.b64encode(b"alice:secret").decode()
            req = Request(f"{base}/hello.txt")
            req.add_header("Authorization", f"Basic {creds}")
            resp = urlopen(req)
            assert resp.headers["Cache-Control"] == "no-store"
        finally:
            httpd.shutdown()
            httpd.server_close()


# -- Rate limiter (auth.py:207-214, server_auth.py:64-65) --------------------


class TestLoginRateLimiter:
    def test_blocked_during_cooldown(self):
        limiter = LoginRateLimiter()
        ip = "1.2.3.4"
        for _ in range(10):
            limiter.record_failure(ip)
        assert limiter.is_blocked(ip) is True

    def test_not_blocked_after_success(self):
        limiter = LoginRateLimiter()
        ip = "1.2.3.4"
        for _ in range(10):
            limiter.record_failure(ip)
        limiter.record_success(ip)
        assert limiter.is_blocked(ip) is False

    def test_not_blocked_before_max_attempts(self):
        limiter = LoginRateLimiter()
        ip = "1.2.3.4"
        limiter.record_failure(ip)
        assert limiter.is_blocked(ip) is False

    def test_login_blocked_with_429(self, serve_dir):
        """Rate-limited IPs get 429 from the login endpoint."""
        config = _make_config(serve_dir, username="alice", password="secret")
        sessions = SessionStore()
        rate_limiter = LoginRateLimiter()
        # Pre-populate the limiter so requests from 127.0.0.1 are blocked
        for _ in range(10):
            rate_limiter.record_failure("127.0.0.1")

        handler = partial(NeevHandler, config, sessions, rate_limiter)
        httpd = HTTPServer(("127.0.0.1", 0), handler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{port}"
            status, _, _ = _post(
                base,
                "/_neev/login",
                b"username=alice&password=x",
                headers={"Origin": base},
            )
            assert status == 429
        finally:
            httpd.shutdown()
            httpd.server_close()


# -- Selective ZIP on non-directory path (server_zip.py:65-66) ---------------


class TestSelectiveZipNonDirectory:
    def test_post_to_file_returns_404(self, server_ctx):
        _, base, _, _ = server_ctx
        host = base.replace("http://", "")
        status, _, body = _post(
            base,
            "/hello.txt?zip",
            b"items=hello.txt",
            headers={"Origin": f"http://{host}"},
        )
        assert status == 404
        assert b"Directory not found" in body


# -- serve_file OSError path (server_core.py:48-50) --------------------------


class TestServeFileOSError:
    def test_file_open_error_returns_404(self, serve_dir):
        """If path.open() raises OSError, handler sends 404."""
        config = _make_config(serve_dir)
        sessions = SessionStore()
        rate_limiter = LoginRateLimiter()
        handler = partial(NeevHandler, config, sessions, rate_limiter)
        httpd = HTTPServer(("127.0.0.1", 0), handler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{port}"
            with patch("pathlib.Path.open", side_effect=OSError("boom")):
                status, _, body = _get(base, "/hello.txt")
            assert status == 404
            assert b"File not found" in body
        finally:
            httpd.shutdown()
            httpd.server_close()


# -- Selective zip hidden file filtering (zip.py:148-158) --------------------


class TestSelectiveZipHiddenFiltering:
    def test_excludes_hidden_in_selected_directory(self, tmp_path):
        """Selective zip of a directory excludes dotfiles/dotdirs when show_hidden=False."""

        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "visible.txt").write_text("v")
        (tmp_path / "sub" / ".dot").write_text("d")
        (tmp_path / "sub" / ".hidden_dir").mkdir()
        (tmp_path / "sub" / ".hidden_dir" / "x.txt").write_text("x")

        data = create_selective_zip_stream(
            tmp_path, ["sub"], tmp_path, show_hidden=False, max_size=100_000_000
        )
        zf = zipfile.ZipFile(data)
        names = zf.namelist()
        assert "sub/visible.txt" in names
        assert not any(".dot" in n or ".hidden_dir" in n for n in names)

    def test_includes_hidden_when_enabled(self, tmp_path):

        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / ".dot").write_text("d")

        data = create_selective_zip_stream(
            tmp_path, ["sub"], tmp_path, show_hidden=True, max_size=100_000_000
        )
        zf = zipfile.ZipFile(data)
        assert "sub/.dot" in zf.namelist()

    def test_select_nonexistent_item_skipped(self, tmp_path):

        (tmp_path / "real.txt").write_text("r")
        data = create_selective_zip_stream(
            tmp_path,
            ["real.txt", "nonexistent.txt"],
            tmp_path,
            show_hidden=False,
            max_size=100_000_000,
        )
        zf = zipfile.ZipFile(data)
        assert "real.txt" in zf.namelist()
        assert "nonexistent.txt" not in zf.namelist()


# -- log_request with non-digit code (server.py) -----------------------------


class TestLogRequestFallback:
    def test_log_request_non_digit_safe(self):
        """log_request handles non-digit codes without crashing (the '-' sentinel)."""
        with patch("sys.stderr.isatty", return_value=False):
            h = NeevHandler.__new__(NeevHandler)
            h.command = "GET"
            h.path = "/test"
            # Should not raise
            h.log_request("-")
