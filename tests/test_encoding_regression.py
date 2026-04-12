"""Regression tests for issue #101 — per-context encoding of paths.

One test class per finding. Covers the behaviors listed in the issue's
acceptance criteria.
"""

import re
from datetime import UTC, datetime

from neev.fs import FileEntry
from neev.html_entries import entry_href, render_entry_row
from neev.html_nav import render_breadcrumb_html
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
