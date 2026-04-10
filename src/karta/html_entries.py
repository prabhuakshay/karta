"""HTML rendering for individual file/directory entries.

Handles table rows (desktop), cards (mobile) for directory listings.
File-type-aware icons with Lumina color coding.
All user-controlled content is escaped via ``html.escape()``.
"""

import html
from pathlib import PurePosixPath

from karta.fs import FileEntry


# -- File type classification -------------------------------------------------

_CODE_EXTS = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".go",
    ".rs",
    ".rb",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".sh",
    ".bash",
    ".zsh",
    ".html",
    ".css",
    ".scss",
    ".vue",
    ".svelte",
}
_CONFIG_EXTS = {
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".ini",
    ".cfg",
    ".conf",
    ".env",
    ".xml",
    ".lock",
}
_DOC_EXTS = {".md", ".txt", ".rst", ".pdf", ".doc", ".docx", ".csv"}
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico"}
_ARCHIVE_EXTS = {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar"}


def _file_type_color(name: str) -> str:
    """Return a Tailwind text color class based on file extension.

    Args:
        name: The filename.

    Returns:
        Tailwind color class string.
    """
    ext = PurePosixPath(name).suffix.lower()
    if ext in _CODE_EXTS:
        return "text-sage-400"
    if ext in _CONFIG_EXTS:
        return "text-amber-500"
    if ext in _DOC_EXTS:
        return "text-cyan-500"
    if ext in _IMAGE_EXTS:
        return "text-ruby-500"
    if ext in _ARCHIVE_EXTS:
        return "text-ink-500"
    return "text-ink-300"


# -- SVG icons ----------------------------------------------------------------

_FOLDER_SVG = '<path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/>'

_FILE_SVG = (
    '<path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 '
    "2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 "
    '01-2 2H6a2 2 0 01-2-2V4z" clip-rule="evenodd"/>'
)


def _icon(entry: FileEntry) -> str:
    """Build an SVG icon element with file-type-aware coloring.

    Args:
        entry: The file entry.

    Returns:
        HTML SVG element string.
    """
    if entry.is_dir:
        color = "text-sage-400"
        path = _FOLDER_SVG
    else:
        color = _file_type_color(entry.name)
        path = _FILE_SVG
    return (
        f'<svg class="w-5 h-5 {color} shrink-0" '
        f'fill="currentColor" viewBox="0 0 20 20">{path}</svg>'
    )


# -- Formatting helpers -------------------------------------------------------


def format_size(size: int) -> str:
    """Format a byte count as a human-readable string.

    Args:
        size: Size in bytes.

    Returns:
        Formatted string: bytes for < 1 KB, then KB/MB/GB with one decimal.
    """
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / (1024 * 1024 * 1024):.1f} GB"


def format_date(entry: FileEntry) -> str:
    """Format a FileEntry's modification time.

    Args:
        entry: The file entry.

    Returns:
        Date string in ``YYYY-MM-DD HH:MM`` format.
    """
    return entry.modified.strftime("%Y-%m-%d %H:%M")


def entry_href(entry: FileEntry, request_path: str) -> str:
    """Build the href for a directory entry.

    Args:
        entry: The file entry.
        request_path: The current request URL path.

    Returns:
        URL-safe href string.
    """
    base = request_path.rstrip("/") + "/"
    name = html.escape(entry.name)
    if entry.is_dir:
        return f"{base}{name}/"
    return f"{base}{name}"


def _ext_badge(name: str) -> str:
    """Render a small file extension badge.

    Args:
        name: The filename.

    Returns:
        HTML span with the extension, or empty string for dirs.
    """
    ext = PurePosixPath(name).suffix.lower()
    if not ext:
        return ""
    return (
        f'<span class="ml-2 px-1.5 py-0.5 text-[10px] font-medium '
        f"uppercase tracking-wide rounded bg-surface-2 "
        f'text-ink-400 hidden lg:inline">{html.escape(ext)}</span>'
    )


# -- Entry renderers ----------------------------------------------------------


def render_entry_row(entry: FileEntry, request_path: str) -> str:
    """Render a single file/directory entry as a table row.

    Args:
        entry: The file entry.
        request_path: The current request URL path.

    Returns:
        HTML ``<tr>`` string.
    """
    href = entry_href(entry, request_path)
    name = html.escape(entry.name)
    size = "\u2014" if entry.is_dir else format_size(entry.size)
    date = format_date(entry)
    icon_html = _icon(entry)
    badge = "" if entry.is_dir else _ext_badge(entry.name)
    name_cls = "text-ink-800 font-medium" if entry.is_dir else "text-ink-700"

    return (
        f'<tr class="group hover:bg-sage-50 '
        f'transition-colors duration-100">'
        f'<td class="px-4 py-3">'
        f'<a href="{href}" class="flex items-center gap-3 '
        f"{name_cls} group-hover:text-sage-500 "
        f'transition-colors duration-150">'
        f"{icon_html}"
        f'<span class="truncate text-sm">{name}</span>{badge}'
        f"</a></td>"
        f'<td class="px-4 py-3 text-right text-sm '
        f"text-ink-400 font-mono tabular-nums whitespace-nowrap "
        f'hidden sm:table-cell">{size}</td>'
        f'<td class="px-4 py-3 text-right text-xs '
        f"text-ink-400 tabular-nums whitespace-nowrap "
        f'hidden md:table-cell">{date}</td>'
        f"</tr>"
    )


def render_entry_card(entry: FileEntry, request_path: str) -> str:
    """Render a single file/directory entry as a mobile card.

    Args:
        entry: The file entry.
        request_path: The current request URL path.

    Returns:
        HTML card string for mobile layout.
    """
    href = entry_href(entry, request_path)
    name = html.escape(entry.name)
    size = "\u2014" if entry.is_dir else format_size(entry.size)
    date = format_date(entry)
    icon_html = _icon(entry)
    name_cls = "text-ink-800 font-medium" if entry.is_dir else "text-ink-700"

    return (
        f'<a href="{href}" class="flex items-center gap-3 '
        f"px-4 py-3.5 hover:bg-sage-50 "
        f'transition-colors duration-100">'
        f"{icon_html}"
        f'<div class="min-w-0 flex-1">'
        f'<div class="{name_cls} truncate text-sm">{name}</div>'
        f'<div class="text-xs text-ink-400 mt-0.5">'
        f"{size} &middot; {date}</div>"
        f"</div>"
        f'<svg class="w-4 h-4 text-ink-300 shrink-0" fill="none" '
        f'stroke="currentColor" viewBox="0 0 24 24">'
        f'<path stroke-linecap="round" stroke-linejoin="round" '
        f'stroke-width="2" d="M9 5l7 7-7 7"/></svg>'
        f"</a>"
    )
