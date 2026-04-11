"""Filesystem operations and path traversal protection for neev.

This module is the security boundary: every filesystem access goes through
``resolve_safe_path`` to ensure paths stay within the served directory.
"""

import logging
import mimetypes
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from urllib.parse import quote


logger = logging.getLogger(__name__)


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

    ``base_dir`` is expected to be already resolved to its real path (done
    once at startup by ``Config.__post_init__``).

    Args:
        base_dir: The root directory being served (must be absolute and
            already realpath-resolved).
        request_path: The URL-decoded path from the HTTP request.

    Returns:
        The resolved path if it is within base_dir, or ``None`` if it escapes.
    """
    base = str(base_dir)
    joined = os.path.join(base, request_path.lstrip("/"))
    real_path = os.path.realpath(joined)

    if real_path == base:
        return Path(real_path)
    if not real_path.startswith(base + os.sep):
        return None
    return Path(real_path)


def get_mime_type(path: Path) -> str:
    """Guess the MIME type of a file from its name.

    Args:
        path: Path to the file (need not exist; only the name is used).

    Returns:
        A MIME type string. Falls back to ``application/octet-stream`` if
        the type cannot be guessed from the file extension.
    """
    content_type, _ = mimetypes.guess_type(str(path))
    return content_type or "application/octet-stream"


_PREVIEWABLE_PREFIXES = ("text/", "image/", "video/", "audio/")
_PREVIEWABLE_TYPES = {"application/pdf", "application/json"}


def is_previewable_type(mime_type: str) -> bool:
    """Check whether a MIME type is safe for inline browser display.

    Args:
        mime_type: A MIME type string (e.g. ``image/png``).

    Returns:
        ``True`` if browsers can typically render the type inline.
    """
    if mime_type in _PREVIEWABLE_TYPES:
        return True
    return mime_type.startswith(_PREVIEWABLE_PREFIXES)


_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def format_content_disposition(disposition: str, filename: str) -> str:
    """Format a Content-Disposition header with safe filename encoding.

    Produces an RFC 6266 header with both an ASCII ``filename`` parameter
    (quotes and backslashes escaped, control characters stripped) and an
    RFC 5987 ``filename*`` parameter for full Unicode support.

    Args:
        disposition: The disposition type (``"attachment"`` or ``"inline"``).
        filename: The raw filename to encode.

    Returns:
        A properly formatted Content-Disposition header value.
    """
    safe = _CONTROL_CHARS.sub("", filename)
    safe = safe.replace("\\", "\\\\").replace('"', '\\"')
    encoded = quote(filename, safe="")
    return f"{disposition}; filename=\"{safe}\"; filename*=UTF-8''{encoded}"


_HIDDEN_FILES = {"neev.toml"}

_MARKDOWN_EXTENSIONS = {".md", ".markdown", ".mdown", ".mkd", ".mkdn"}


def is_markdown_file(path: Path | PurePosixPath) -> bool:
    """Check whether a file path has a markdown extension.

    Args:
        path: Path to check (only the suffix is inspected).

    Returns:
        ``True`` if the file extension is a known markdown variant.
    """
    return path.suffix.lower() in _MARKDOWN_EXTENSIONS


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
    with os.scandir(path) as it:
        for entry in it:
            if entry.name in _HIDDEN_FILES:
                continue
            if not show_hidden and entry.name.startswith("."):
                continue
            try:
                stat = entry.stat()
            except OSError:
                logger.warning("skipping %s: stat() failed", entry.path)
                continue
            is_dir = entry.is_dir()
            entries.append(
                FileEntry(
                    name=entry.name,
                    is_dir=is_dir,
                    size=0 if is_dir else stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                )
            )
    entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))
    return entries
