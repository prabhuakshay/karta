"""Regression tests for issue #101 — per-context encoding of paths.

One test class per finding. Covers the behaviors listed in the issue's
acceptance criteria.
"""

import http.client
import re
import threading
from datetime import UTC, datetime
from functools import partial
from http.server import HTTPServer
from io import BytesIO
from urllib.parse import quote
from urllib.request import Request, urlopen
from zipfile import ZipFile

from neev.auth import LoginRateLimiter, SessionStore
from neev.config import Config
from neev.fs import FileEntry
from neev.html_entries import entry_href, render_entry_row
from neev.html_nav import render_breadcrumb_html
from neev.server import NeevHandler
from neev.server_preview import serve_generic_preview


def _file(name: str, is_dir: bool = False) -> FileEntry:
    return FileEntry(name=name, is_dir=is_dir, size=0, modified=datetime(2026, 1, 1, tzinfo=UTC))


# -- Finding #1: entry_href and breadcrumbs ----------------------------------


class TestEntryHrefHtmlInjection:
    """Finding #1 — decoded request_path was concatenated raw into hrefs."""

    def test_request_path_with_quote_is_encoded(self):
        href = entry_href(_file("file.txt"), '/has"quote/')
        assert '"' not in href.replace('"', "", 0)  # no raw unencoded "
        # %22 is the URL encoding of "
        assert "%22" in href

    def test_request_path_with_ampersand_encoded(self):
        href = entry_href(_file("a"), "/a&b/")
        assert "&" not in href or "%26" in href

    def test_request_path_with_space_encoded(self):
        href = entry_href(_file("f"), "/a b/")
        assert "%20" in href

    def test_row_renders_quote_safely(self):
        row = render_entry_row(_file("x"), '/a"b/')
        # href attribute value must not contain a raw "
        # (the attribute is double-quoted, a raw " would break it)
        # Extract the href attribute
        m = re.search(r'<a href="([^"]*)"', row)
        assert m is not None
        href_val = m.group(1)
        assert '"' not in href_val


# -- Finding #4: upload redirect Location URL-encoded -----------------------


class TestUploadRedirectLocation:
    """Finding #4 — Location header contained decoded path verbatim."""

    def test_mkdir_redirect_location_url_encoded(self, tmp_path):
        (tmp_path / "has space").mkdir()
        cfg = Config(
            directory=tmp_path,
            host="127.0.0.1",
            port=0,
            username=None,
            password=None,
            show_hidden=False,
            enable_zip_download=False,
            max_zip_size=104857600,
            enable_upload=True,
        )
        sessions = SessionStore()
        handler = partial(NeevHandler, cfg, sessions, LoginRateLimiter())
        httpd = HTTPServer(("127.0.0.1", 0), handler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port)
            conn.request(
                "POST",
                "/has%20space/?mkdir=new",
                headers={
                    "Origin": f"http://127.0.0.1:{port}",
                    "Host": f"127.0.0.1:{port}",
                },
            )
            resp = conn.getresponse()
            resp.read()
            assert resp.status == 303
            location = resp.getheader("Location") or ""
            assert "%20" in location
            assert " " not in location
        finally:
            httpd.shutdown()
            httpd.server_close()


# -- Finding #3: selective zip item name decoding ---------------------------


class TestSelectiveZipDecoding:
    """Finding #3 — parse_qs already URL-decodes; unquote() ran twice."""

    def test_items_with_literal_percent_reachable(self, tmp_path):
        """A filename containing a literal ``%`` must survive the POST decode."""
        # File with a literal '%' in the name
        (tmp_path / "a%b.txt").write_text("data")

        cfg = Config(
            directory=tmp_path,
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
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            # Form body quotes '%' as %25 — after parse_qs it decodes to '%'
            # Before the fix, unquote() ran again and produced empty string
            body = ("items=" + quote("a%b.txt", safe="")).encode()
            req = Request(
                f"http://127.0.0.1:{port}/?zip",
                data=body,
                method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp = urlopen(req)
            assert resp.status == 200
            zf = ZipFile(BytesIO(resp.read()))
            assert "a%b.txt" in zf.namelist()
        finally:
            httpd.shutdown()
            httpd.server_close()


# -- Finding #2: preview URLs ------------------------------------------------


class TestPreviewUrlEncoding:
    """Finding #2 — preview URLs were html-escaped but not URL-encoded."""

    def test_image_preview_src_url_encoded(self, tmp_path):
        p = tmp_path / "has space.png"
        p.write_bytes(b"x")

        class _Stub:
            def __init__(self):
                self.body = b""
                self.status = None
                self.headers = []

            def send_response(self, s):
                self.status = s

            def send_header(self, k, v):
                self.headers.append((k, v))

            def end_headers(self):
                pass

            class _W:
                def __init__(self, parent):
                    self.parent = parent

                def write(self, b):
                    self.parent.body += b

            @property
            def wfile(self):
                return self._W(self)

        h = _Stub()
        serve_generic_preview(h, p, "/has space.png", "image/png")  # type: ignore[arg-type]
        assert b"%20" in h.body
        assert b' src="/has space.png"' not in h.body


class TestBreadcrumbHrefEncoding:
    def test_breadcrumb_href_encodes_special_chars(self):
        crumbs = [("~", "/"), ('a"b', '/a"b/'), ("leaf", '/a"b/leaf/')]
        out = render_breadcrumb_html(crumbs)
        # middle crumb is a link — href must be URL-encoded
        assert 'href="/a%22b/"' in out
