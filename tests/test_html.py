from datetime import UTC, datetime
from pathlib import Path

from neev.fs import FileEntry
from neev.html import render_directory_listing
from neev.html_entries import (
    _ext_badge,
    entry_href,
    format_date,
    format_size,
    render_entry_card,
    render_entry_row,
)
from neev.html_icons import icon_for_entry
from neev.html_nav import build_breadcrumbs, build_summary, parent_link


# -- Fixtures ----------------------------------------------------------------

_NOW = datetime(2025, 6, 15, 10, 30, tzinfo=UTC)

_DIR_ENTRY = FileEntry(name="docs", is_dir=True, size=0, modified=_NOW)
_FILE_ENTRY = FileEntry(name="readme.md", is_dir=False, size=2048, modified=_NOW)
_XSS_ENTRY = FileEntry(
    name='<script>alert("xss")</script>',
    is_dir=False,
    size=100,
    modified=_NOW,
)


# -- format_size -------------------------------------------------------------


class TestFormatSize:
    def test_bytes(self):
        assert format_size(512) == "512 B"

    def test_kilobytes(self):
        assert format_size(2048) == "2.0 KB"

    def test_megabytes(self):
        assert format_size(5 * 1024 * 1024) == "5.0 MB"

    def test_gigabytes(self):
        assert format_size(3 * 1024 * 1024 * 1024) == "3.0 GB"

    def test_zero(self):
        assert format_size(0) == "0 B"


# -- format_date -------------------------------------------------------------


class TestFormatDate:
    def test_format(self):
        assert format_date(_FILE_ENTRY) == "2025-06-15 10:30"


# -- entry_href --------------------------------------------------------------


class TestEntryHref:
    def test_file_href(self):
        assert entry_href(_FILE_ENTRY, "/docs") == "/docs/readme.md"

    def test_dir_href(self):
        assert entry_href(_DIR_ENTRY, "/") == "/docs/"

    def test_trailing_slash(self):
        assert entry_href(_FILE_ENTRY, "/path/") == "/path/readme.md"


# -- build_breadcrumbs ------------------------------------------------------


class TestBuildBreadcrumbs:
    def test_root(self, tmp_path):
        crumbs = build_breadcrumbs(tmp_path, tmp_path)
        assert len(crumbs) == 1
        assert crumbs[0] == ("~", "/")

    def test_one_level(self, tmp_path):
        sub = tmp_path / "docs"
        sub.mkdir()
        crumbs = build_breadcrumbs(sub, tmp_path)
        assert len(crumbs) == 2
        assert crumbs[1] == ("docs", "/docs/")

    def test_nested(self, tmp_path):
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        crumbs = build_breadcrumbs(nested, tmp_path)
        assert len(crumbs) == 3
        assert crumbs[1][1] == "/a/"
        assert crumbs[2][1] == "/a/b/"

    def test_unrelated_path(self, tmp_path):
        crumbs = build_breadcrumbs(Path("/unrelated"), tmp_path)
        assert len(crumbs) == 1


# -- parent_link ------------------------------------------------------------


class TestParentLink:
    def test_root(self):
        assert parent_link("/") == "/"

    def test_one_level(self):
        assert parent_link("/docs/") == "/"

    def test_nested(self):
        assert parent_link("/a/b/c/") == "/a/b/"


# -- build_summary ----------------------------------------------------------


class TestBuildSummary:
    def test_empty(self):
        assert build_summary([]) == "Empty directory"

    def test_files_only(self):
        assert build_summary([_FILE_ENTRY]) == "1 file"

    def test_dirs_only(self):
        assert build_summary([_DIR_ENTRY, _DIR_ENTRY]) == "2 folders"

    def test_mixed(self):
        assert build_summary([_DIR_ENTRY, _FILE_ENTRY]) == "1 folder, 1 file"


# -- render_entry_row --------------------------------------------------------


class TestRenderEntryRow:
    def test_dir_row(self):
        row = render_entry_row(_DIR_ENTRY, "/")
        assert "<tr" in row
        assert "docs" in row
        assert "\u2014" in row

    def test_file_row(self):
        row = render_entry_row(_FILE_ENTRY, "/")
        assert "readme.md" in row
        assert "2.0 KB" in row

    def test_xss_escaped(self):
        row = render_entry_row(_XSS_ENTRY, "/")
        assert "<script>" not in row
        assert "&lt;script&gt;" in row


# -- render_entry_card -------------------------------------------------------


class TestRenderEntryCard:
    def test_dir_card(self):
        card = render_entry_card(_DIR_ENTRY, "/")
        assert "docs" in card

    def test_file_card(self):
        card = render_entry_card(_FILE_ENTRY, "/")
        assert "readme.md" in card
        assert "2.0 KB" in card

    def test_xss_escaped(self):
        card = render_entry_card(_XSS_ENTRY, "/")
        assert "<script>" not in card
        assert "&lt;script&gt;" in card


# -- render_directory_listing ------------------------------------------------


class TestRenderDirectoryListing:
    def test_full_page(self, tmp_path):
        entries = [_DIR_ENTRY, _FILE_ENTRY]
        page = render_directory_listing(
            path=tmp_path,
            entries=entries,
            base_dir=tmp_path,
            request_path="/",
        )
        assert "<!DOCTYPE html>" in page
        assert "docs" in page
        assert "readme.md" in page
        assert "neev.css" in page
        assert "alpine.min.js" in page

    def test_subdirectory_has_parent_link(self, tmp_path):
        sub = tmp_path / "docs"
        sub.mkdir()
        page = render_directory_listing(
            path=sub,
            entries=[_FILE_ENTRY],
            base_dir=tmp_path,
            request_path="/docs/",
        )
        assert ".." in page

    def test_root_no_parent_link(self, tmp_path):
        page = render_directory_listing(
            path=tmp_path,
            entries=[],
            base_dir=tmp_path,
            request_path="/",
        )
        # Parent back-arrow icon not present at root
        assert "M15 19l-7-7" not in page

    def test_empty_directory(self, tmp_path):
        page = render_directory_listing(
            path=tmp_path,
            entries=[],
            base_dir=tmp_path,
            request_path="/",
        )
        assert "This directory is empty" in page

    def test_zip_link_shown_when_enabled(self, tmp_path):
        page = render_directory_listing(
            path=tmp_path,
            entries=[],
            base_dir=tmp_path,
            request_path="/",
            enable_zip_download=True,
        )
        assert "Download ZIP" in page
        assert "?zip" in page

    def test_zip_link_hidden_when_disabled(self, tmp_path):
        page = render_directory_listing(
            path=tmp_path,
            entries=[],
            base_dir=tmp_path,
            request_path="/",
            enable_zip_download=False,
        )
        assert "Download ZIP" not in page

    def test_zip_link_href_for_subdirectory(self, tmp_path):
        sub = tmp_path / "builds"
        sub.mkdir()
        page = render_directory_listing(
            path=sub,
            entries=[],
            base_dir=tmp_path,
            request_path="/builds/",
            enable_zip_download=True,
        )
        assert "/builds/?zip" in page


# -- icon_for_entry ----------------------------------------------------------


class TestIconForEntry:
    def test_folder_icon(self):
        svg = icon_for_entry("docs", is_dir=True)
        assert "text-sage-400" in svg
        assert 'fill="currentColor"' in svg

    def test_python_icon(self):
        svg = icon_for_entry("main.py", is_dir=False)
        assert "text-sage-400" in svg
        assert "12.5" in svg

    def test_js_icon(self):
        svg = icon_for_entry("app.js", is_dir=False)
        assert "text-amber-500" in svg

    def test_config_icon(self):
        svg = icon_for_entry("config.toml", is_dir=False)
        assert "text-amber-500" in svg

    def test_document_icon(self):
        svg = icon_for_entry("readme.md", is_dir=False)
        assert "text-cyan-500" in svg

    def test_image_icon(self):
        svg = icon_for_entry("photo.png", is_dir=False)
        assert "text-ruby-500" in svg

    def test_archive_icon(self):
        svg = icon_for_entry("backup.zip", is_dir=False)
        assert "text-ink-500" in svg

    def test_unknown_fallback(self):
        svg = icon_for_entry("data.xyz", is_dir=False)
        assert "text-ink-300" in svg

    def test_shell_icon(self):
        svg = icon_for_entry("deploy.sh", is_dir=False)
        assert "text-sage-400" in svg

    def test_markup_icon(self):
        svg = icon_for_entry("index.html", is_dir=False)
        assert "text-ruby-500" in svg

    def test_css_icon(self):
        svg = icon_for_entry("style.css", is_dir=False)
        assert "text-cyan-500" in svg


# -- _ext_badge --------------------------------------------------------------


class TestExtBadge:
    def test_with_extension(self):
        badge = _ext_badge("readme.md")
        assert ".md" in badge
        assert "<span" in badge

    def test_no_extension(self):
        assert _ext_badge("Makefile") == ""

    def test_escapes_html(self):
        badge = _ext_badge("file.<b>bad</b>")
        assert "<b>" not in badge
