"""File upload handling for neev.

Provides multipart form data parsing (stdlib-only, no ``cgi`` module),
filename sanitization, size validation, and folder creation.
"""

import logging
import os
import re
from pathlib import Path


logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB


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


def _parse_multipart(body: bytes, boundary: bytes) -> list[tuple[str, str, bytes]]:
    """Parse a multipart/form-data body into its parts.

    Args:
        body: The raw request body.
        boundary: The boundary string from the Content-Type header.

    Returns:
        List of ``(field_name, filename, data)`` tuples.
        For non-file fields, filename is empty string.

    Raises:
        UploadError: If the body cannot be parsed.
    """
    delimiter = b"--" + boundary
    parts = body.split(delimiter)

    # First part is empty (before first boundary), last is "--\r\n" (closing)
    results: list[tuple[str, str, bytes]] = []

    for part in parts[1:]:
        if part.startswith(b"--"):
            break

        # Split headers from body at the double CRLF
        header_end = part.find(b"\r\n\r\n")
        if header_end == -1:
            continue

        raw_headers = part[:header_end].decode("utf-8", errors="replace")
        # Body is between headers and trailing CRLF before next boundary
        data = part[header_end + 4 :]
        if data.endswith(b"\r\n"):
            data = data[:-2]

        disposition = ""
        for line in raw_headers.split("\r\n"):
            lower = line.lower()
            if lower.startswith("content-disposition:"):
                disposition = line.split(":", 1)[1].strip()
                break

        if not disposition:
            continue

        params = _parse_content_disposition(disposition)
        field_name = params.get("name", "")
        filename = params.get("filename", "")
        results.append((field_name, filename, data))

    return results


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
    body: bytes,
    content_type: str,
    content_length: int,
    target_dir: Path,
    base_dir: Path,
) -> list[str]:
    """Parse a multipart upload, validate, and save file(s).

    Args:
        body: The raw request body bytes.
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
    parts = _parse_multipart(body, boundary)

    # Pair each file with its preceding relativePath hidden field.
    # Each relativePath field applies to the immediately following file part.
    file_parts: list[tuple[str, str, bytes]] = []  # (rel_path, filename, data)
    pending_rel_path = ""

    for field_name, filename, data in parts:
        if field_name == "relativePath" and not filename:
            pending_rel_path = data.decode("utf-8", errors="replace")
        elif filename:
            file_parts.append((pending_rel_path, filename, data))
            pending_rel_path = ""

    if not file_parts:
        raise UploadError("No file provided")

    saved: list[str] = []

    for rel_path, raw_filename, data in file_parts:
        if rel_path and "/" in rel_path:
            # Folder upload — preserve directory structure
            safe_rel = _sanitize_relative_path(rel_path)
            save_dir = target_dir / os.path.dirname(safe_rel)
            safe_name = sanitize_filename(raw_filename)
        else:
            # Regular file upload
            save_dir = target_dir
            safe_name = sanitize_filename(raw_filename)

        # Ensure subdirectories exist (no-op for regular uploads)
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / safe_name

        # Path containment check — use realpath to catch symlink escapes
        real_save = os.path.realpath(save_path)
        real_base = os.path.realpath(base_dir)
        if not real_save.startswith(real_base + os.sep):  # pragma: no cover — defense-in-depth
            raise UploadError(f"Path traversal blocked for '{raw_filename}'")

        save_path.write_bytes(data)
        logger.info("Saved upload: %s (%d bytes)", save_path, len(data))
        saved.append(safe_name)

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
