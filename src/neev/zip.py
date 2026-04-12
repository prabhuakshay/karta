"""On-the-fly streaming ZIP archive generation for neev directories.

Writes ZIP output directly into the client's response body via a size-tracking
writer wrapper. Peak memory is flat regardless of archive size, and the size
cap is enforced before each file is added so a single oversized file cannot
defeat ``max_zip_size``.

Every file path is re-validated through ``fs.resolve_safe_path`` as
defense-in-depth against path traversal.
"""

import logging
import os
import zipfile
from pathlib import Path
from typing import Protocol

from neev.fs import resolve_safe_path


logger = logging.getLogger(__name__)


class _Writable(Protocol):
    """Minimal file-like writer interface used by ZIP streaming."""

    def write(self, data: bytes, /) -> int: ...
    def flush(self) -> None: ...


class ZipSizeLimitError(Exception):
    """Raised when the ZIP archive exceeds the configured size limit."""


class _SizeTrackingWriter:
    """File-like wrapper that counts bytes and enforces a cap.

    ``zipfile`` expects a writable file object. We expose ``write``, ``tell``
    and ``flush`` — the minimum needed by ``ZipFile`` in write mode — and
    raise ``ZipSizeLimitError`` as soon as the running byte count exceeds
    ``max_size``.
    """

    def __init__(self, wfile: _Writable, max_size: int) -> None:
        self._wfile = wfile
        self._max_size = max_size
        self._written = 0

    def write(self, data: bytes) -> int:
        self._written += len(data)
        if self._written > self._max_size:
            raise ZipSizeLimitError(
                f"ZIP archive exceeds {self._max_size // (1024 * 1024)} MB limit"
            )
        self._wfile.write(data)
        return len(data)

    def tell(self) -> int:
        return self._written

    def flush(self) -> None:
        self._wfile.flush()

    def close(self) -> None:
        self._wfile.flush()

    @property
    def bytes_written(self) -> int:
        return self._written


class _ChunkedWriter:
    """Wraps a wfile and emits HTTP chunked-transfer-encoding frames.

    Each ``write`` becomes one chunk. ``close`` writes the terminating
    zero-length chunk. Empty writes are dropped (chunk size zero is the
    terminator and must not appear mid-stream).
    """

    def __init__(self, wfile: _Writable) -> None:
        self._wfile = wfile

    def write(self, data: bytes) -> int:
        if not data:
            return 0
        self._wfile.write(f"{len(data):x}\r\n".encode("ascii"))
        self._wfile.write(data)
        self._wfile.write(b"\r\n")
        return len(data)

    def flush(self) -> None:
        self._wfile.flush()

    def close(self) -> None:
        self._wfile.write(b"0\r\n\r\n")
        self._wfile.flush()


def _check_cap(current: int, file_size: int, max_size: int) -> None:
    """Raise if adding ``file_size`` more bytes would exceed the cap.

    The check uses the on-disk file size as an upper bound on the bytes the
    compressor can emit for this entry (compression cannot make a file larger
    in practice, and ``ZIP_DEFLATED`` will only make it smaller). Checking
    before ``zf.write`` prevents the previous bypass where a multi-GB file
    was fully buffered before the post-write size check fired.
    """
    if current + file_size > max_size:
        raise ZipSizeLimitError(f"ZIP archive exceeds {max_size // (1024 * 1024)} MB limit")


def _iter_files(
    root: Path,
    show_hidden: bool,
) -> list[tuple[Path, str]]:
    """Collect ``(full_path, arcname)`` pairs under ``root``.

    ``arcname`` is relative to ``root`` — callers pick ``root`` to produce the
    archive layout they want.
    """
    entries: list[tuple[Path, str]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        if not show_hidden:
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for filename in filenames:
            if not show_hidden and filename.startswith("."):
                continue
            full_path = Path(dirpath) / filename
            arcname = str(full_path.relative_to(root))
            entries.append((full_path, arcname))
    return entries


def _write_zip(
    writer: _SizeTrackingWriter,
    entries: list[tuple[Path, str]],
    base_dir: Path,
    max_size: int,
) -> None:
    """Write each entry into a ZipFile backed by ``writer``."""
    with zipfile.ZipFile(writer, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for full_path, arcname in entries:
            safe = resolve_safe_path(base_dir, str(full_path.relative_to(base_dir)))
            if safe is None:  # pragma: no cover
                logger.warning("skipping path outside base dir: %s", full_path)
                continue
            try:
                file_size = full_path.stat().st_size
            except OSError:  # pragma: no cover
                logger.warning("could not stat %s, skipping", full_path)
                continue
            _check_cap(writer.bytes_written, file_size, max_size)
            zf.write(full_path, arcname)


def _selected_entries(
    directory: Path,
    items: list[str],
    base_dir: Path,
    show_hidden: bool,
) -> list[tuple[Path, str]]:
    """Resolve selected ``items`` under ``directory`` into entry pairs."""
    entries: list[tuple[Path, str]] = []
    for item_name in items:
        item_path = directory / item_name
        safe = resolve_safe_path(base_dir, str(item_path.relative_to(base_dir)))
        if safe is None or not safe.exists():
            logger.warning("skipping invalid item: %s", item_name)
            continue
        if safe.is_file():
            entries.append((safe, item_name))
        elif safe.is_dir():
            for full_path, arcname in _iter_files(safe, show_hidden):
                entries.append((full_path, str(Path(item_name) / arcname)))
    return entries


def write_zip(
    out: _Writable,
    directory: Path,
    base_dir: Path,
    show_hidden: bool,
    max_size: int,
) -> None:
    """Write a ZIP of ``directory`` into a generic writable stream.

    Raw ZIP bytes — no HTTP framing. Tests use this directly; HTTP callers use
    ``stream_zip`` which wraps this in chunked transfer encoding.

    Raises:
        ZipSizeLimitError: If the archive would exceed ``max_size``.
    """
    writer = _SizeTrackingWriter(out, max_size)
    _write_zip(writer, _iter_files(directory, show_hidden), base_dir, max_size)


def write_selective_zip(
    out: _Writable,
    directory: Path,
    items: list[str],
    base_dir: Path,
    show_hidden: bool,
    max_size: int,
) -> None:
    """Write a selective ZIP into a generic writable stream. See ``write_zip``."""
    writer = _SizeTrackingWriter(out, max_size)
    entries = _selected_entries(directory, items, base_dir, show_hidden)
    _write_zip(writer, entries, base_dir, max_size)


def stream_zip(
    wfile: _Writable,
    directory: Path,
    base_dir: Path,
    show_hidden: bool,
    max_size: int,
) -> None:
    """Stream a ZIP into ``wfile`` using HTTP chunked transfer encoding.

    The caller must have already emitted response headers including
    ``Transfer-Encoding: chunked``.

    Raises:
        ZipSizeLimitError: If the archive would exceed ``max_size``.
    """
    chunked = _ChunkedWriter(wfile)
    try:
        write_zip(chunked, directory, base_dir, show_hidden, max_size)
    finally:
        chunked.close()


def stream_selective_zip(
    wfile: _Writable,
    directory: Path,
    items: list[str],
    base_dir: Path,
    show_hidden: bool,
    max_size: int,
) -> None:
    """Stream a selective ZIP into ``wfile`` using HTTP chunked transfer encoding."""
    chunked = _ChunkedWriter(wfile)
    try:
        write_selective_zip(chunked, directory, items, base_dir, show_hidden, max_size)
    finally:
        chunked.close()
