"""File upload handling for neev.

Exposes the save and folder-creation surface. Low-level multipart stream
parsing lives in ``upload_multipart``.
"""

import io
import logging
import os
import shutil
import tempfile
from pathlib import Path

from neev.upload_multipart import UploadError, _extract_boundary, _MultipartStream


__all__ = [
    "MAX_UPLOAD_SIZE",
    "UploadError",
    "handle_create_folder",
    "handle_upload",
    "sanitize_filename",
]


logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB


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
    cleaned = raw.replace("\\", "/")
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


def _save_part(
    filename: str,
    data: tempfile.SpooledTemporaryFile[bytes],
    target_dir: Path,
    base_dir: Path,
    rel_path: str,
) -> str:
    """Write a single file part to disk, enforcing path containment.

    Args:
        filename: Raw filename from the multipart header.
        data: Sought-to-zero spooled temp file holding the part body.
        target_dir: Directory uploads are saved into.
        base_dir: Served root (for path-traversal containment).
        rel_path: Optional ``webkitRelativePath`` carried by the preceding
            ``relativePath`` field; used to preserve folder-upload structure.

    Returns:
        The sanitized filename that was saved.

    Raises:
        UploadError: On sanitization or containment failure.
    """
    if rel_path and "/" in rel_path:
        safe_rel = _sanitize_relative_path(rel_path)
        save_dir = target_dir / os.path.dirname(safe_rel)
    else:
        save_dir = target_dir

    safe_name = sanitize_filename(filename)
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / safe_name

    real_save = os.path.realpath(save_path)
    real_base = os.path.realpath(base_dir)
    if not real_save.startswith(real_base + os.sep):  # pragma: no cover
        raise UploadError(f"Path traversal blocked for '{filename}'")

    if save_path.exists():
        raise UploadError(f"'{safe_name}' already exists")

    with save_path.open("wb") as dest:
        shutil.copyfileobj(data, dest)
    logger.info("Saved upload: %s", save_path)
    return safe_name


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
            saved.append(_save_part(filename, data, target_dir, base_dir, pending_rel_path))
            pending_rel_path = ""
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
