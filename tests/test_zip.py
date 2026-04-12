"""Tests for neev.zip — streaming ZIP archive generation."""

import io
import zipfile

import pytest

from neev.zip import ZipSizeLimitError, write_selective_zip, write_zip


def _make_zip(directory, base_dir=None, *, show_hidden=False, max_size=100_000_000):
    buf = io.BytesIO()
    write_zip(buf, directory, base_dir or directory, show_hidden, max_size)
    buf.seek(0)
    return buf


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "a.txt").write_text("alpha")
    (tmp_path / "b.txt").write_text("bravo")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.txt").write_text("charlie")
    return tmp_path


@pytest.fixture
def hidden_tree(tree):
    (tree / ".secret").write_text("hidden file")
    dot_dir = tree / ".hidden_dir"
    dot_dir.mkdir()
    (dot_dir / "inside.txt").write_text("inside hidden dir")
    return tree


class TestWriteZip:
    def test_returns_valid_zip(self, tree):
        zf = zipfile.ZipFile(_make_zip(tree))
        assert zf.testzip() is None

    def test_contains_all_files(self, tree):
        zf = zipfile.ZipFile(_make_zip(tree))
        assert set(zf.namelist()) == {"a.txt", "b.txt", "sub/c.txt"}

    def test_file_contents_correct(self, tree):
        zf = zipfile.ZipFile(_make_zip(tree))
        assert zf.read("a.txt") == b"alpha"
        assert zf.read("sub/c.txt") == b"charlie"

    def test_empty_directory_produces_valid_zip(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        zf = zipfile.ZipFile(_make_zip(empty, base_dir=tmp_path))
        assert zf.namelist() == []


class TestHiddenFileFiltering:
    def test_excludes_hidden_files_by_default(self, hidden_tree):
        zf = zipfile.ZipFile(_make_zip(hidden_tree))
        names = zf.namelist()
        assert ".secret" not in names
        assert not any(".hidden_dir" in n for n in names)

    def test_includes_hidden_files_when_enabled(self, hidden_tree):
        zf = zipfile.ZipFile(_make_zip(hidden_tree, show_hidden=True))
        names = set(zf.namelist())
        assert ".secret" in names
        assert ".hidden_dir/inside.txt" in names


class TestZipSizeLimit:
    def test_raises_on_size_limit(self, tree):
        with pytest.raises(ZipSizeLimitError, match="MB limit"):
            _make_zip(tree, max_size=1)

    def test_prewrite_check_rejects_oversized_file_without_buffering(self, tmp_path):
        """A single file larger than max_size must be rejected before any bytes
        of it are written into the archive. This closes the pre-v0.1.0 bypass
        where the post-write size check allowed the whole file to buffer first.
        """
        big = tmp_path / "big.bin"
        big.write_bytes(b"x" * 10_000)

        buf = io.BytesIO()
        with pytest.raises(ZipSizeLimitError):
            write_zip(buf, tmp_path, tmp_path, show_hidden=False, max_size=500)
        # Central directory aside, the oversized file's contents must not have
        # been copied into the output.
        assert len(buf.getvalue()) < 1000

    def test_multiple_files_accumulate_against_cap(self, tmp_path):
        for i in range(3):
            (tmp_path / f"f{i}.bin").write_bytes(b"x" * 400)
        buf = io.BytesIO()
        with pytest.raises(ZipSizeLimitError):
            write_zip(buf, tmp_path, tmp_path, show_hidden=False, max_size=500)


class TestSubdirectoryZip:
    def test_zip_subdirectory(self, tree):
        sub = tree / "sub"
        zf = zipfile.ZipFile(_make_zip(sub, base_dir=tree))
        assert set(zf.namelist()) == {"c.txt"}


class TestSelectiveZip:
    def test_selected_file(self, tree):
        buf = io.BytesIO()
        write_selective_zip(buf, tree, ["a.txt"], tree, show_hidden=False, max_size=100_000_000)
        buf.seek(0)
        zf = zipfile.ZipFile(buf)
        assert set(zf.namelist()) == {"a.txt"}
        assert zf.read("a.txt") == b"alpha"

    def test_selected_directory(self, tree):
        buf = io.BytesIO()
        write_selective_zip(buf, tree, ["sub"], tree, show_hidden=False, max_size=100_000_000)
        buf.seek(0)
        zf = zipfile.ZipFile(buf)
        assert set(zf.namelist()) == {"sub/c.txt"}

    def test_invalid_item_skipped(self, tree):
        buf = io.BytesIO()
        write_selective_zip(
            buf, tree, ["does_not_exist"], tree, show_hidden=False, max_size=100_000_000
        )
        buf.seek(0)
        zf = zipfile.ZipFile(buf)
        assert zf.namelist() == []

    def test_size_cap_enforced(self, tree):
        buf = io.BytesIO()
        with pytest.raises(ZipSizeLimitError):
            write_selective_zip(buf, tree, ["a.txt", "b.txt"], tree, show_hidden=False, max_size=1)
