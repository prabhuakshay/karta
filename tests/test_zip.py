"""Tests for neev.zip — ZIP archive generation."""

import zipfile

import pytest

from neev.zip import ZipSizeLimitError, create_zip_stream


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

    def test_size_check_uses_compressed_size(self, tmp_path):
        """The size check must use actual compressed buffer size, not uncompressed file size.

        A highly-compressible file (1000 repeated bytes) compresses well below
        its uncompressed size. The old check mixed compressed buffer position
        with uncompressed file size, causing premature rejection.
        """
        compressible = tmp_path / "compressible.txt"
        compressible.write_bytes(b"a" * 1000)

        # max_size is larger than compressed output but smaller than
        # uncompressed — old check would reject, new check allows it
        data = create_zip_stream(tmp_path, tmp_path, show_hidden=False, max_size=500)
        zf = zipfile.ZipFile(data)
        assert zf.read("compressible.txt") == b"a" * 1000

    def test_raises_when_compressed_output_exceeds_limit(self, tmp_path):
        """The error fires when the actual compressed buffer exceeds max_size."""
        big = tmp_path / "big.bin"
        # Random-ish bytes that don't compress well
        big.write_bytes(bytes(range(256)) * 4)

        with pytest.raises(ZipSizeLimitError):
            create_zip_stream(tmp_path, tmp_path, show_hidden=False, max_size=100)


# -- Subdirectory zipping ----------------------------------------------------


class TestSubdirectoryZip:
    def test_zip_subdirectory(self, tree):
        sub = tree / "sub"
        data = create_zip_stream(sub, tree, show_hidden=False, max_size=100_000_000)
        zf = zipfile.ZipFile(data)
        assert set(zf.namelist()) == {"c.txt"}
