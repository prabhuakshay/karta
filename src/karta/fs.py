"""Filesystem operations and path traversal protection for karta.

This module is the security boundary: every filesystem access goes through
``resolve_safe_path`` to ensure paths stay within the served directory.
"""

import mimetypes
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class FileEntry:
    """A single item in a directory listing.

    Attributes:
        name: Filename or directory name.
        is_dir: Whether this entry is a directory.
        size: Size in bytes (0 for directories).
        modified: Last-modified timestamp in UTC.
    """

    name: str
    is_dir: bool
    size: int
    modified: datetime


def resolve_safe_path(base_dir: Path, request_path: str) -> Path | None:
    """Resolve a request path to a real filesystem path within base_dir.

    Uses ``os.path.realpath`` to resolve symlinks and ``..`` components,
    then verifies the result is inside base_dir. Returns ``None`` if the
    path escapes the served directory.

    Args:
        base_dir: The root directory being served (must be absolute).
        request_path: The URL-decoded path from the HTTP request.

    Returns:
        The resolved path if it is within base_dir, or ``None`` if it escapes.
    """
    real_base = os.path.realpath(base_dir)
    joined = os.path.join(real_base, request_path.lstrip("/"))
    real_path = os.path.realpath(joined)

    if real_path == real_base:
        return Path(real_path)
    if not real_path.startswith(real_base + os.sep):
        return None
    return Path(real_path)


def read_file(path: Path) -> tuple[bytes, str]:
    """Read a file and guess its MIME type.

    Args:
        path: Absolute path to the file to read.

    Returns:
        A ``(content, content_type)`` tuple. Falls back to
        ``application/octet-stream`` if the type cannot be guessed.
    """
    content = path.read_bytes()
    content_type, _ = mimetypes.guess_type(str(path))
    return content, content_type or "application/octet-stream"


def list_directory(path: Path, show_hidden: bool) -> list[FileEntry]:
    """List a directory's contents as FileEntry objects.

    Entries are sorted: directories first, then files, both alphabetically.
    Hidden entries (names starting with ``.``) are excluded unless
    ``show_hidden`` is ``True``.

    Args:
        path: Absolute path to the directory to list.
        show_hidden: Whether to include dotfiles and dotdirs.

    Returns:
        A sorted list of ``FileEntry`` objects.
    """
    entries: list[FileEntry] = []
    for item in path.iterdir():
        if not show_hidden and item.name.startswith("."):
            continue
        stat = item.stat()
        entries.append(
            FileEntry(
                name=item.name,
                is_dir=item.is_dir(),
                size=0 if item.is_dir() else stat.st_size,
                modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            )
        )
    entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))
    return entries
