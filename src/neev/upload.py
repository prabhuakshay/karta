"""File upload handling for neev.

Provides multipart form data parsing (stdlib-only, no ``cgi`` module),
filename sanitization, size validation, and folder creation.
"""

import io
import logging
import os
import re
import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path


logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB
_CHUNK_SIZE = 65_536  # 64 KB read chunks
_SPOOL_MAX = 1_048_576  # 1 MB before SpooledTemporaryFile spills to disk


class UploadError(Exception):
    """Raised when an upload fails validation."""


# -- Multipart parsing --------------------------------------------------------


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
        header_line: The raw header line (e.g. ``form-data; name="file"; filename="test.txt"``).

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


# -- Filename sanitization ---------------------------------------------------


def sanitize_filename(raw: str) -> str:
    """Sanitize a filename from an upload, stripping path components.

    Handles both forward and back slashes, ``..`` components, and
    leading/trailing whitespace. Returns the basename only.

    Args:
        raw: The raw filename from the multipart header.

    Returns:
        The sanitized filename.

    Raises:
        UploadError: If the filename is empty after sanitization.
    """
    # Null bytes can truncate paths at the C level — always a red flag
    if "\x00" in raw:
        raise UploadError("Filename contains null byte")
    # Replace backslashes (Windows paths uploaded from browsers)
    cleaned = raw.replace("\\", "/")
    # Take only the final path component
    name = os.path.basename(cleaned).strip()
    if not name or name in (".", ".."):
        raise UploadError("Empty filename after sanitization")
    return name


def _sanitize_relative_path(raw: str) -> str:
    """Sanitize a relative path from a folder upload (webkitRelativePath).

    Preserves the directory structure but strips dangerous components.

    Args:
        raw: The raw relative path (e.g. ``folder/sub/file.txt``).

    Returns:
        Sanitized relative path with no ``..`` or absolute components.

    Raises:
        UploadError: If the path is empty after sanitization.
    """
    cleaned = raw.replace("\\", "/")
    parts = [p.strip() for p in cleaned.split("/") if p.strip() and p.strip() != ".."]
    if not parts:
        raise UploadError("Empty path after sanitization")
    return os.path.join(*parts)


# -- Upload handling ----------------------------------------------------------


def handle_upload(
    rfile: io.BufferedIOBase,
    content_type: str,
    content_length: int,
    target_dir: Path,
    base_dir: Path,
) -> list[str]:
    """Parse a multipart upload stream, validate, and save file(s).

    Reads from *rfile* in chunks so peak memory stays flat regardless
    of upload size.

    Args:
        rfile: Readable stream positioned at the start of the request body.
        content_type: The Content-Type header value.
        content_length: The Content-Length header value.
        target_dir: The directory to save uploaded files to.
        base_dir: The served root directory (for path containment).

    Returns:
        List of saved filenames.

    Raises:
        UploadError: If validation fails (size, filename, path).
    """
    if content_length > MAX_UPLOAD_SIZE:
        raise UploadError(
            f"Upload too large ({content_length // (1024 * 1024)} MB). "
            f"Maximum is {MAX_UPLOAD_SIZE // (1024 * 1024)} MB."
        )

    boundary = _extract_boundary(content_type)
    stream = _MultipartStream(rfile, content_length, boundary)

    saved: list[str] = []
    pending_rel_path = ""

    for field_name, filename, data in stream.parts():
        if isinstance(data, bytes):
            if field_name == "relativePath" and not filename:
                pending_rel_path = data.decode("utf-8", errors="replace")
            continue

        if not filename:
            data.close()
            continue

        try:
            if pending_rel_path and "/" in pending_rel_path:
                safe_rel = _sanitize_relative_path(pending_rel_path)
                save_dir = target_dir / os.path.dirname(safe_rel)
            else:
                save_dir = target_dir

            safe_name = sanitize_filename(filename)
            pending_rel_path = ""

            save_dir.mkdir(parents=True, exist_ok=True)
            save_path = save_dir / safe_name

            real_save = os.path.realpath(save_path)
            real_base = os.path.realpath(base_dir)
            if not real_save.startswith(real_base + os.sep):  # pragma: no cover
                raise UploadError(f"Path traversal blocked for '{filename}'")

            with save_path.open("wb") as dest:
                shutil.copyfileobj(data, dest)
            logger.info("Saved upload: %s", save_path)
            saved.append(safe_name)
        finally:
            data.close()

    if not saved:
        raise UploadError("No file provided")

    return saved


# -- Folder creation ----------------------------------------------------------


def handle_create_folder(
    folder_name: str,
    target_dir: Path,
    base_dir: Path,
) -> str:
    """Create a new folder inside the target directory.

    Args:
        folder_name: The raw folder name from the form.
        target_dir: The directory to create the folder in.
        base_dir: The served root directory (for path containment).

    Returns:
        The sanitized folder name.

    Raises:
        UploadError: If validation fails (empty name, path traversal).
    """
    safe_name = sanitize_filename(folder_name)
    folder_path = target_dir / safe_name

    real_folder = os.path.realpath(folder_path)
    real_base = os.path.realpath(base_dir)
    if not real_folder.startswith(real_base + os.sep):  # pragma: no cover — defense-in-depth
        raise UploadError(f"Path traversal blocked for '{folder_name}'")

    if folder_path.exists():
        raise UploadError(f"'{safe_name}' already exists")

    folder_path.mkdir(parents=False)
    logger.info("Created folder: %s", folder_path)
    return safe_name
