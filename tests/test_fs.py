from datetime import UTC, datetime

from karta.fs import FileEntry, list_directory, read_file, resolve_safe_path


# -- resolve_safe_path -------------------------------------------------------


class TestResolveSafePath:
    def test_valid_file(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hello")
        result = resolve_safe_path(tmp_path, "/readme.txt")
        assert result == tmp_path / "readme.txt"

    def test_valid_subdir_file(self, tmp_path):
        sub = tmp_path / "docs"
        sub.mkdir()
        (sub / "guide.md").write_text("# Guide")
        result = resolve_safe_path(tmp_path, "/docs/guide.md")
        assert result == sub / "guide.md"

    def test_root_path(self, tmp_path):
        result = resolve_safe_path(tmp_path, "/")
        assert result == tmp_path.resolve()

    def test_empty_path(self, tmp_path):
        result = resolve_safe_path(tmp_path, "")
        assert result == tmp_path.resolve()

    def test_dot_dot_traversal_blocked(self, tmp_path):
        result = resolve_safe_path(tmp_path, "/../../../etc/passwd")
        assert result is None

    def test_many_dot_dots_blocked(self, tmp_path):
        result = resolve_safe_path(tmp_path, "/../../../../../../../../etc/shadow")
        assert result is None

    def test_dot_dot_in_middle_blocked(self, tmp_path):
        (tmp_path / "subdir").mkdir()
        result = resolve_safe_path(tmp_path, "/subdir/../../etc/passwd")
        assert result is None

    def test_symlink_inside_allowed(self, tmp_path):
        target = tmp_path / "real.txt"
        target.write_text("content")
        link = tmp_path / "link.txt"
        link.symlink_to(target)
        result = resolve_safe_path(tmp_path, "/link.txt")
        assert result == target.resolve()

    def test_symlink_outside_blocked(self, tmp_path):
        outside = tmp_path.parent / "outside_target.txt"
        outside.write_text("secret")
        try:
            link = tmp_path / "escape.txt"
            link.symlink_to(outside)
            result = resolve_safe_path(tmp_path, "/escape.txt")
            assert result is None
        finally:
            outside.unlink()

    def test_nonexistent_path_returns_path(self, tmp_path):
        result = resolve_safe_path(tmp_path, "/nonexistent.txt")
        assert result is not None
        assert result == tmp_path / "nonexistent.txt"

    def test_directory_path(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        result = resolve_safe_path(tmp_path, "/subdir")
        assert result == sub


# -- read_file ---------------------------------------------------------------


class TestReadFile:
    def test_reads_content(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("hello world")
        content, _ = read_file(f)
        assert content == b"hello world"

    def test_html_mime(self, tmp_path):
        f = tmp_path / "page.html"
        f.write_text("<h1>Hi</h1>")
        _, content_type = read_file(f)
        assert content_type == "text/html"

    def test_json_mime(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text("{}")
        _, content_type = read_file(f)
        assert content_type == "application/json"

    def test_css_mime(self, tmp_path):
        f = tmp_path / "style.css"
        f.write_text("body {}")
        _, content_type = read_file(f)
        assert content_type == "text/css"

    def test_js_mime(self, tmp_path):
        f = tmp_path / "app.js"
        f.write_text("console.log(1)")
        _, content_type = read_file(f)
        assert "javascript" in content_type

    def test_png_mime(self, tmp_path):
        f = tmp_path / "image.png"
        f.write_bytes(b"\x89PNG")
        _, content_type = read_file(f)
        assert content_type == "image/png"

    def test_pdf_mime(self, tmp_path):
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF")
        _, content_type = read_file(f)
        assert content_type == "application/pdf"

    def test_unknown_extension_fallback(self, tmp_path):
        f = tmp_path / "data.xyz123"
        f.write_bytes(b"\x00\x01")
        _, content_type = read_file(f)
        assert content_type == "application/octet-stream"

    def test_binary_content(self, tmp_path):
        f = tmp_path / "data.bin"
        data = bytes(range(256))
        f.write_bytes(data)
        content, _ = read_file(f)
        assert content == data


# -- list_directory ----------------------------------------------------------


class TestListDirectory:
    def test_empty_directory(self, tmp_path):
        assert list_directory(tmp_path, show_hidden=False) == []

    def test_files_listed(self, tmp_path):
        (tmp_path / "a.txt").write_text("aaa")
        (tmp_path / "b.txt").write_text("bbb")
        entries = list_directory(tmp_path, show_hidden=False)
        names = [e.name for e in entries]
        assert names == ["a.txt", "b.txt"]

    def test_directories_first(self, tmp_path):
        (tmp_path / "file.txt").write_text("x")
        (tmp_path / "adir").mkdir()
        entries = list_directory(tmp_path, show_hidden=False)
        assert entries[0].name == "adir"
        assert entries[0].is_dir is True
        assert entries[1].name == "file.txt"
        assert entries[1].is_dir is False

    def test_hidden_files_excluded_by_default(self, tmp_path):
        (tmp_path / ".hidden").write_text("secret")
        (tmp_path / "visible.txt").write_text("public")
        entries = list_directory(tmp_path, show_hidden=False)
        names = [e.name for e in entries]
        assert ".hidden" not in names
        assert "visible.txt" in names

    def test_hidden_files_included_when_enabled(self, tmp_path):
        (tmp_path / ".hidden").write_text("secret")
        (tmp_path / "visible.txt").write_text("public")
        entries = list_directory(tmp_path, show_hidden=True)
        names = [e.name for e in entries]
        assert ".hidden" in names
        assert "visible.txt" in names

    def test_hidden_dirs_excluded(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / "src").mkdir()
        entries = list_directory(tmp_path, show_hidden=False)
        names = [e.name for e in entries]
        assert ".git" not in names
        assert "src" in names

    def test_directory_size_is_zero(self, tmp_path):
        (tmp_path / "subdir").mkdir()
        entries = list_directory(tmp_path, show_hidden=False)
        assert entries[0].size == 0

    def test_file_size_is_correct(self, tmp_path):
        f = tmp_path / "data.txt"
        f.write_text("12345")
        entries = list_directory(tmp_path, show_hidden=False)
        assert entries[0].size == 5

    def test_modified_is_utc_datetime(self, tmp_path):
        (tmp_path / "file.txt").write_text("x")
        entries = list_directory(tmp_path, show_hidden=False)
        assert isinstance(entries[0].modified, datetime)
        assert entries[0].modified.tzinfo is UTC

    def test_alphabetical_within_groups(self, tmp_path):
        (tmp_path / "Zebra.txt").write_text("z")
        (tmp_path / "alpha.txt").write_text("a")
        (tmp_path / "beta.txt").write_text("b")
        entries = list_directory(tmp_path, show_hidden=False)
        names = [e.name for e in entries]
        assert names == ["alpha.txt", "beta.txt", "Zebra.txt"]


# -- FileEntry ---------------------------------------------------------------


class TestFileEntry:
    def test_frozen(self):
        entry = FileEntry(
            name="test.txt",
            is_dir=False,
            size=100,
            modified=datetime.now(tz=UTC),
        )
        assert entry.name == "test.txt"
        assert entry.is_dir is False
        assert entry.size == 100
