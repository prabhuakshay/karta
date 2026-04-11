"""Tests for karta.zip — ZIP archive generation."""

import zipfile

import pytest

from karta.zip import ZipSizeLimitError, create_zip_stream


# -- Fixtures ----------------------------------------------------------------


@pytest.fixture
def tree(tmp_path):
    """Create a directory tree for ZIP tests."""
    (tmp_path / "a.txt").write_text("alpha")
    (tmp_path / "b.txt").write_text("bravo")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.txt").write_text("charlie")
    return tmp_path


@pytest.fixture
def hidden_tree(tree):
    """Add hidden files and dirs to the tree."""
    (tree / ".secret").write_text("hidden file")
    dot_dir = tree / ".hidden_dir"
    dot_dir.mkdir()
    (dot_dir / "inside.txt").write_text("inside hidden dir")
    return tree


# -- Basic functionality -----------------------------------------------------


class TestCreateZipStream:
    def test_returns_valid_zip(self, tree):
        data = create_zip_stream(tree, tree, show_hidden=False, max_size=100_000_000)
        zf = zipfile.ZipFile(data)
        assert zf.testzip() is None

    def test_contains_all_files(self, tree):
        data = create_zip_stream(tree, tree, show_hidden=False, max_size=100_000_000)
        zf = zipfile.ZipFile(data)
        names = set(zf.namelist())
        assert names == {"a.txt", "b.txt", "sub/c.txt"}

    def test_file_contents_correct(self, tree):
        data = create_zip_stream(tree, tree, show_hidden=False, max_size=100_000_000)
        zf = zipfile.ZipFile(data)
        assert zf.read("a.txt") == b"alpha"
        assert zf.read("sub/c.txt") == b"charlie"

    def test_relative_paths_not_absolute(self, tree):
        data = create_zip_stream(tree, tree, show_hidden=False, max_size=100_000_000)
        zf = zipfile.ZipFile(data)
        for name in zf.namelist():
            assert not name.startswith("/")

    def test_empty_directory_produces_valid_zip(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        data = create_zip_stream(empty, tmp_path, show_hidden=False, max_size=100_000_000)
        zf = zipfile.ZipFile(data)
        assert zf.namelist() == []


# -- Hidden file filtering ---------------------------------------------------


class TestHiddenFileFiltering:
    def test_excludes_hidden_files_by_default(self, hidden_tree):
        data = create_zip_stream(hidden_tree, hidden_tree, show_hidden=False, max_size=100_000_000)
        zf = zipfile.ZipFile(data)
        names = zf.namelist()
        assert ".secret" not in names
        assert not any(".hidden_dir" in n for n in names)

    def test_includes_hidden_files_when_enabled(self, hidden_tree):
        data = create_zip_stream(hidden_tree, hidden_tree, show_hidden=True, max_size=100_000_000)
        zf = zipfile.ZipFile(data)
        names = set(zf.namelist())
        assert ".secret" in names
        assert ".hidden_dir/inside.txt" in names


# -- Size limit --------------------------------------------------------------


class TestZipSizeLimit:
    def test_raises_on_size_limit(self, tree):
        with pytest.raises(ZipSizeLimitError, match="MB limit"):
            create_zip_stream(tree, tree, show_hidden=False, max_size=1)

    def test_size_check_fires_before_write(self, tmp_path):
        """Regression: buffer must not grow past max_size before the error is raised.

        The check must run before zf.write(), not after. A 200-byte file against
        a 100-byte limit should raise without growing the buffer beyond 100 bytes.
        """
        big = tmp_path / "big.txt"
        big.write_bytes(b"x" * 200)

        with pytest.raises(ZipSizeLimitError):
            create_zip_stream(tmp_path, tmp_path, show_hidden=False, max_size=100)


# -- Subdirectory zipping ----------------------------------------------------


class TestSubdirectoryZip:
    def test_zip_subdirectory(self, tree):
        sub = tree / "sub"
        data = create_zip_stream(sub, tree, show_hidden=False, max_size=100_000_000)
        zf = zipfile.ZipFile(data)
        assert set(zf.namelist()) == {"c.txt"}
