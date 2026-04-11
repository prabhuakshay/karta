"""On-the-fly ZIP archive generation for karta directories.

Builds a ZIP in memory using ``zipfile`` + ``io.BytesIO``. Each file is
validated through ``fs.resolve_safe_path`` as defense-in-depth against
path traversal, even though the directory itself was already validated.
"""

import io
import logging
import os
import zipfile
from pathlib import Path

from karta.fs import resolve_safe_path


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
                # Check uncompressed file size against remaining budget before writing.
                # This ensures the buffer never grows beyond max_size, even for a single
                # large file. Using uncompressed size is conservative but correct — we
                # want to cap memory usage, not compressed output size.
                if buf.tell() + os.path.getsize(full_path) > max_size:
                    raise ZipSizeLimitError(
                        f"ZIP archive exceeds {max_size // (1024 * 1024)} MB limit"
                    )
                zf.write(full_path, arcname)

    buf.seek(0)
    return buf
