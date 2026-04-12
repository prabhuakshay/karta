"""Streaming multipart/form-data parser for neev uploads.

Stdlib-only replacement for the deprecated ``cgi`` module. Reads the
request body in chunks, writing file parts to ``SpooledTemporaryFile``
so peak memory stays flat regardless of upload size.
"""

import io
import re
import tempfile
from collections.abc import Generator


_CHUNK_SIZE = 65_536  # 64 KB read chunks
_SPOOL_MAX = 1_048_576  # 1 MB before SpooledTemporaryFile spills to disk


class UploadError(Exception):
    """Raised when an upload fails validation or parsing."""


def _extract_boundary(content_type: str) -> bytes:
    """Extract the multipart boundary from a Content-Type header.

    Args:
        content_type: The raw Content-Type header value.

    Returns:
        The boundary bytes.

    Raises:
        UploadError: If the boundary cannot be found.
    """
    # Quoted form: boundary="val with spaces"; unquoted form: boundary=val
    match = re.search(r'boundary=(?:"([^"]+)"|([^\s;]+))', content_type)
    if not match:
        raise UploadError("Missing multipart boundary")
    return (match.group(1) or match.group(2)).encode("ascii")


def _parse_content_disposition(header_line: str) -> dict[str, str]:
    """Parse a Content-Disposition header into a dict of key-value pairs.

    Args:
        header_line: The raw header line
            (e.g. ``form-data; name="file"; filename="test.txt"``).

    Returns:
        Dict with keys like ``name`` and ``filename``.
    """
    params: dict[str, str] = {}
    for match in re.finditer(r'(\w+)="([^"]*)"', header_line):
        params[match.group(1)] = match.group(2)
    return params


class _MultipartStream:
    """Streaming multipart/form-data parser that avoids buffering the full body.

    Reads from *rfile* in chunks.  File parts are written to
    ``SpooledTemporaryFile`` objects (in-memory up to ``_SPOOL_MAX``,
    then spill to disk).  Non-file fields stay as ``bytes``.
    """

    def __init__(self, rfile: io.BufferedIOBase, content_length: int, boundary: bytes) -> None:
        self._rfile = rfile
        self._remaining = content_length
        self._buf = b""
        self._boundary = b"--" + boundary
        self._delimiter = b"\r\n" + self._boundary

    # -- low-level buffer helpers ---------------------------------------------

    def _fill(self, target: int = _CHUNK_SIZE) -> None:
        """Ensure the buffer has at least *target* bytes (or the stream is exhausted)."""
        while len(self._buf) < target and self._remaining > 0:
            n = min(target - len(self._buf), self._remaining)
            chunk = self._rfile.read(n)
            if not chunk:
                break
            self._remaining -= len(chunk)
            self._buf += chunk

    def _find(self, marker: bytes) -> int:
        """Fill and search for *marker*.  Returns index or ``-1``."""
        while True:
            idx = self._buf.find(marker)
            if idx != -1:
                return idx
            if self._remaining <= 0:
                return -1
            self._fill()

    def _skip_past(self, marker: bytes) -> bool:
        """Advance the buffer past *marker*.  Returns ``False`` if not found."""
        idx = self._find(marker)
        if idx == -1:
            return False
        self._buf = self._buf[idx + len(marker) :]
        return True

    # -- part iteration -------------------------------------------------------

    def parts(
        self,
    ) -> Generator[tuple[str, str, bytes | tempfile.SpooledTemporaryFile[bytes]],]:
        """Yield ``(field_name, filename, data)`` for each part.

        *data* is ``bytes`` for non-file fields and a sought-to-zero
        ``SpooledTemporaryFile`` for file fields.
        """
        if not self._skip_past(self._boundary):
            return

        while True:
            self._fill(2)
            if not self._buf or self._buf.startswith(b"--"):
                return
            if self._buf.startswith(b"\r\n"):
                self._buf = self._buf[2:]

            hdr_end = self._find(b"\r\n\r\n")
            if hdr_end == -1:
                return

            raw_headers = self._buf[:hdr_end].decode("utf-8", errors="replace")
            self._buf = self._buf[hdr_end + 4 :]

            disposition = ""
            for line in raw_headers.split("\r\n"):
                if line.lower().startswith("content-disposition:"):
                    disposition = line.split(":", 1)[1].strip()
                    break

            if not disposition:
                self._skip_past(self._delimiter)
                continue

            params = _parse_content_disposition(disposition)
            field_name = params.get("name", "")
            filename = params.get("filename", "")

            if filename:
                tmp = tempfile.SpooledTemporaryFile(max_size=_SPOOL_MAX)  # noqa: SIM115
                self._read_body(tmp)
                tmp.seek(0)
                yield field_name, filename, tmp
            else:
                buf = io.BytesIO()
                self._read_body(buf)
                yield field_name, filename, buf.getvalue()

    def _read_body(self, output: io.BytesIO | tempfile.SpooledTemporaryFile) -> None:
        """Stream part body into *output* until the next boundary delimiter."""
        dlen = len(self._delimiter)

        while True:
            self._fill(dlen + _CHUNK_SIZE)

            idx = self._buf.find(self._delimiter)
            if idx != -1:
                output.write(self._buf[:idx])
                self._buf = self._buf[idx + dlen :]
                return

            # Flush bytes that cannot be part of a partial delimiter match
            safe = len(self._buf) - dlen + 1
            if safe > 0:
                output.write(self._buf[:safe])
                self._buf = self._buf[safe:]

            if self._remaining <= 0:
                output.write(self._buf)
                self._buf = b""
                return
