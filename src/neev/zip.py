"""On-the-fly ZIP archive generation for neev directories.

Builds a ZIP in memory using ``zipfile`` + ``io.BytesIO``. Each file is
validated through ``fs.resolve_safe_path`` as defense-in-depth against
path traversal, even though the directory itself was already validated.
"""

import io
import logging
import os
import zipfile
from pathlib import Path

from neev.fs import resolve_safe_path


logger = logging.getLogger(__name__)


class ZipSizeLimitError(Exception):
    """Raised when the ZIP archive exceeds the configured size limit."""


def create_zip_stream(
    directory: Path,
    base_dir: Path,
    show_hidden: bool,
    max_size: int,
) -> io.BytesIO:
    """Create a ZIP archive of a directory's contents and return a stream.

    Walks the directory recursively, filtering hidden files unless
    ``show_hidden`` is ``True``. Every file path is re-validated against
    ``base_dir`` before inclusion.

    The returned ``BytesIO`` is sought to position 0 and ready to read.
    Callers should read (or copy) from it directly rather than calling
    ``getvalue()``, which would create a redundant second copy in memory.

    Args:
        directory: The directory to archive.
        base_dir: The served root directory (security boundary).
        show_hidden: Whether to include dotfiles and dotdirs.
        max_size: Maximum allowed size of the ZIP buffer in bytes.

    Returns:
        A ``BytesIO`` stream containing the complete ZIP archive, sought to 0.

    Raises:
        ZipSizeLimitError: If the archive exceeds ``max_size``.
    """
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(directory):
            if not show_hidden:
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]

            for filename in filenames:
                if not show_hidden and filename.startswith("."):
                    continue
                full_path = Path(dirpath) / filename

                safe = resolve_safe_path(base_dir, str(full_path.relative_to(base_dir)))
                if safe is None:  # pragma: no cover
                    logger.warning("skipping path outside base dir: %s", full_path)
                    continue

                arcname = str(full_path.relative_to(directory))
                zf.write(full_path, arcname)
                if buf.tell() > max_size:
                    raise ZipSizeLimitError(
                        f"ZIP archive exceeds {max_size // (1024 * 1024)} MB limit"
                    )

    buf.seek(0)
    return buf


def _add_file_to_zip(
    zf: zipfile.ZipFile,
    buf: io.BytesIO,
    full_path: Path,
    arcname: str,
    base_dir: Path,
    max_size: int,
) -> None:
    """Validate and add a single file to a ZIP archive.

    Args:
        zf: The open ZipFile to write into.
        buf: The underlying BytesIO buffer (for size checks).
        full_path: Absolute path to the file on disk.
        arcname: Archive-internal path for this entry.
        base_dir: The served root directory (security boundary).
        max_size: Maximum allowed buffer size in bytes.

    Raises:
        ZipSizeLimitError: If the buffer exceeds ``max_size`` after writing.
    """
    safe = resolve_safe_path(base_dir, str(full_path.relative_to(base_dir)))
    if safe is None:  # pragma: no cover
        logger.warning("skipping path outside base dir: %s", full_path)
        return

    zf.write(full_path, arcname)
    if buf.tell() > max_size:
        raise ZipSizeLimitError(f"ZIP archive exceeds {max_size // (1024 * 1024)} MB limit")


def create_selective_zip_stream(
    directory: Path,
    items: list[str],
    base_dir: Path,
    show_hidden: bool,
    max_size: int,
) -> io.BytesIO:
    """Create a ZIP archive containing only the selected items.

    Each item name is resolved relative to ``directory``. Files are added
    directly; directories are walked recursively.

    Args:
        directory: The parent directory containing the selected items.
        items: List of filenames/dirnames within ``directory`` to include.
        base_dir: The served root directory (security boundary).
        show_hidden: Whether to include dotfiles and dotdirs.
        max_size: Maximum allowed size of the ZIP buffer in bytes.

    Returns:
        A ``BytesIO`` stream containing the ZIP archive, sought to 0.

    Raises:
        ZipSizeLimitError: If the archive exceeds ``max_size``.
    """
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for item_name in items:
            item_path = directory / item_name
            safe = resolve_safe_path(base_dir, str(item_path.relative_to(base_dir)))
            if safe is None or not safe.exists():
                logger.warning("skipping invalid item: %s", item_name)
                continue

            if safe.is_file():
                _add_file_to_zip(zf, buf, safe, item_name, base_dir, max_size)
            elif safe.is_dir():
                for dirpath, dirnames, filenames in os.walk(safe):
                    if not show_hidden:
                        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                    for filename in filenames:
                        if not show_hidden and filename.startswith("."):
                            continue
                        full_path = Path(dirpath) / filename
                        arcname = str(full_path.relative_to(directory))
                        _add_file_to_zip(zf, buf, full_path, arcname, base_dir, max_size)

    buf.seek(0)
    return buf
