"""Unit tests for upload module: parsing, sanitization, and file handling."""

import io
from pathlib import Path

import pytest

from neev.upload import (
    MAX_UPLOAD_SIZE,
    UploadError,
    _extract_boundary,
    _MultipartStream,
    _parse_content_disposition,
    _sanitize_relative_path,
    handle_create_folder,
    handle_upload,
    sanitize_filename,
)


# -- Fixtures -----------------------------------------------------------------


@pytest.fixture
def serve_dir(tmp_path):
    """Create a temp directory for upload tests."""
    (tmp_path / "existing.txt").write_text("already here")
    sub = tmp_path / "subdir"
    sub.mkdir()
    return tmp_path


# -- Helpers ------------------------------------------------------------------


def _build_multipart(files: list[tuple[str, str, bytes]], boundary: str = "testboundary"):
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


def _parse_stream(body: bytes, boundary: bytes) -> list[tuple[str, str, bytes]]:
    """Helper: run the streaming parser and collect results as plain tuples."""
    stream = _MultipartStream(io.BytesIO(body), len(body), boundary)
    results = []
    for name, fname, data in stream.parts():
        if isinstance(data, bytes):
            results.append((name, fname, data))
        else:
            results.append((name, fname, data.read()))
            data.close()
    return results


# -- Multipart parsing -------------------------------------------------------


class TestExtractBoundary:
    def test_extracts_boundary(self):
        assert _extract_boundary("multipart/form-data; boundary=abc123") == b"abc123"

    def test_quoted_boundary(self):
        assert _extract_boundary('multipart/form-data; boundary="abc123"') == b"abc123"

    def test_quoted_boundary_with_spaces(self):
        # RFC 2046 allows spaces inside a quoted boundary value
        assert _extract_boundary('multipart/form-data; boundary="my boundary"') == b"my boundary"

    def test_missing_boundary_raises(self):
        with pytest.raises(UploadError, match="boundary"):
            _extract_boundary("text/plain")


class TestParseContentDisposition:
    def test_name_and_filename(self):
        params = _parse_content_disposition('form-data; name="file"; filename="test.txt"')
        assert params == {"name": "file", "filename": "test.txt"}

    def test_name_only(self):
        params = _parse_content_disposition('form-data; name="field"')
        assert params == {"name": "field"}


class TestParseMultipart:
    def test_single_file(self):
        body, ct = _build_multipart([("file", "test.txt", b"hello")])
        parts = _parse_stream(body, _extract_boundary(ct))
        assert len(parts) == 1
        assert parts[0] == ("file", "test.txt", b"hello")

    def test_multiple_files(self):
        body, ct = _build_multipart([("file", "a.txt", b"a"), ("file", "b.txt", b"b")])
        assert len(_parse_stream(body, _extract_boundary(ct))) == 2

    def test_non_file_field(self):
        body, ct = _build_multipart([("field", "", b"value")])
        parts = _parse_stream(body, _extract_boundary(ct))
        assert parts[0] == ("field", "", b"value")

    def test_skips_part_without_headers(self):
        assert _parse_stream(b"--b\r\nno double crlf\r\n--b--\r\n", b"b") == []

    def test_skips_part_without_disposition(self):
        raw = b"--b\r\nContent-Type: text/plain\r\n\r\ndata\r\n--b--\r\n"
        assert _parse_stream(raw, b"b") == []

    def test_no_closing_boundary(self):
        raw = b'--b\r\nContent-Disposition: form-data; name="f"; filename="x"\r\n\r\ndata\r\n'
        assert len(_parse_stream(raw, b"b")) == 1

    def test_data_with_closing_boundary(self):
        hdr = b'--b\r\nContent-Disposition: form-data; name="f"; filename="x"\r\n\r\n'
        parts = _parse_stream(hdr + b"data\r\n--b--\r\n", b"b")
        assert len(parts) == 1
        assert parts[0][2] == b"data"


# -- Filename sanitization ---------------------------------------------------


class TestSanitizeFilename:
    def test_simple_filename(self):
        assert sanitize_filename("test.txt") == "test.txt"

    def test_strips_path_components(self):
        assert sanitize_filename("../../etc/passwd") == "passwd"

    def test_strips_backslash_paths(self):
        assert sanitize_filename("C:\\Users\\test\\file.txt") == "file.txt"

    def test_strips_forward_slash_paths(self):
        assert sanitize_filename("/etc/shadow") == "shadow"

    def test_rejects_empty(self):
        with pytest.raises(UploadError, match="Empty filename"):
            sanitize_filename("")

    def test_rejects_dots(self):
        with pytest.raises(UploadError, match="Empty filename"):
            sanitize_filename("..")

    def test_strips_whitespace(self):
        assert sanitize_filename("  test.txt  ") == "test.txt"

    def test_rejects_null_byte(self):
        with pytest.raises(UploadError, match="null byte"):
            sanitize_filename("file\x00.txt")


class TestSanitizeRelativePath:
    def test_preserves_structure(self):
        assert Path(_sanitize_relative_path("folder/sub/file.txt")) == Path("folder/sub/file.txt")

    def test_strips_dotdot(self):
        result = _sanitize_relative_path("../../../etc/passwd")
        assert ".." not in result

    def test_rejects_empty(self):
        with pytest.raises(UploadError, match="Empty path"):
            _sanitize_relative_path("")


# -- handle_upload ------------------------------------------------------------


class TestHandleUpload:
    def test_saves_file(self, serve_dir):
        body, ct = _build_multipart([("file", "new.txt", b"content")])
        saved = handle_upload(io.BytesIO(body), ct, len(body), serve_dir, serve_dir)
        assert "new.txt" in saved
        assert (serve_dir / "new.txt").read_bytes() == b"content"

    def test_rejects_existing(self, serve_dir):
        body, ct = _build_multipart([("file", "existing.txt", b"overwritten")])
        with pytest.raises(UploadError, match="already exists"):
            handle_upload(io.BytesIO(body), ct, len(body), serve_dir, serve_dir)
        assert (serve_dir / "existing.txt").read_text() == "already here"

    def test_rejects_too_large(self, serve_dir):
        body, ct = _build_multipart([("file", "big.txt", b"x")])
        with pytest.raises(UploadError, match="too large"):
            handle_upload(io.BytesIO(body), ct, MAX_UPLOAD_SIZE + 1, serve_dir, serve_dir)

    def test_rejects_no_file(self, serve_dir):
        body, ct = _build_multipart([("field", "", b"value")])
        with pytest.raises(UploadError, match="No file"):
            handle_upload(io.BytesIO(body), ct, len(body), serve_dir, serve_dir)

    def test_sanitizes_traversal_filename(self, serve_dir):
        body, ct = _build_multipart([("file", "../../etc/passwd", b"data")])
        assert handle_upload(io.BytesIO(body), ct, len(body), serve_dir, serve_dir) == ["passwd"]

    def test_multiple_files(self, serve_dir):
        body, ct = _build_multipart([("file", "a.txt", b"aaa"), ("file", "b.txt", b"bbb")])
        assert len(handle_upload(io.BytesIO(body), ct, len(body), serve_dir, serve_dir)) == 2

    def test_folder_upload_with_relative_paths(self, serve_dir):
        body, ct = _build_multipart(
            [
                ("relativePath", "", b"myfolder/sub/file.txt"),
                ("file", "file.txt", b"nested"),
            ]
        )
        handle_upload(io.BytesIO(body), ct, len(body), serve_dir, serve_dir)
        assert (serve_dir / "myfolder" / "sub" / "file.txt").read_bytes() == b"nested"


# -- handle_create_folder -----------------------------------------------------


class TestHandleCreateFolder:
    def test_creates_folder(self, serve_dir):
        assert handle_create_folder("newfolder", serve_dir, serve_dir) == "newfolder"
        assert (serve_dir / "newfolder").is_dir()

    def test_rejects_existing(self, serve_dir):
        (serve_dir / "exists").mkdir()
        with pytest.raises(UploadError, match="already exists"):
            handle_create_folder("exists", serve_dir, serve_dir)

    def test_sanitizes_name(self, serve_dir):
        assert handle_create_folder("../../evil", serve_dir, serve_dir) == "evil"

    def test_rejects_empty_name(self, serve_dir):
        with pytest.raises(UploadError, match="Empty filename"):
            handle_create_folder("", serve_dir, serve_dir)
