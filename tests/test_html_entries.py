"""Tests for html_entries helpers and html_icons icon mapping."""

from neev.html_entries import _ext_badge
from neev.html_icons import icon_for_entry


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
