"""HTML rendering for individual file/directory entries.

Handles table rows (desktop) and cards (mobile) for directory listings.
All user-controlled content is escaped via ``html.escape()``.
"""

import html

from karta.fs import FileEntry


# -- SVG icons ----------------------------------------------------------------

_FOLDER_ICON = (
    '<svg class="w-5 h-5 text-karta-500 shrink-0" fill="currentColor" '
    'viewBox="0 0 20 20"><path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 '
    '012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/></svg>'
)

_FILE_ICON = (
    '<svg class="w-5 h-5 text-slate-400 shrink-0" fill="currentColor" '
    'viewBox="0 0 20 20"><path fill-rule="evenodd" d="M4 4a2 2 0 '
    "012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 "
    '2 0 01-2 2H6a2 2 0 01-2-2V4z" clip-rule="evenodd"/></svg>'
)

_CHEVRON_ICON = (
    '<svg class="w-4 h-4 text-slate-300 shrink-0" fill="none" '
    'stroke="currentColor" viewBox="0 0 24 24">'
    '<path stroke-linecap="round" stroke-linejoin="round" '
    'stroke-width="2" d="M9 5l7 7-7 7"/></svg>'
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


# -- Entry renderers ----------------------------------------------------------


def render_entry_row(entry: FileEntry, request_path: str) -> str:
    """Render a single file/directory entry as a table row (desktop).

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
    icon = _FOLDER_ICON if entry.is_dir else _FILE_ICON
    name_class = "text-karta-700 font-medium" if entry.is_dir else "text-slate-700"

    return (
        f'<tr class="group hover:bg-karta-50/60 transition-colors">'
        f'<td class="py-2.5 pl-4 pr-2">'
        f'<a href="{href}" class="flex items-center gap-2.5 {name_class} '
        f'hover:text-karta-600 transition-colors">'
        f"{icon}"
        f'<span class="truncate">{name}</span>'
        f"</a></td>"
        f'<td class="py-2.5 px-3 text-right text-sm text-slate-500 '
        f'font-mono whitespace-nowrap hidden sm:table-cell">{size}</td>'
        f'<td class="py-2.5 px-3 pr-4 text-right text-sm text-slate-400 '
        f'whitespace-nowrap hidden md:table-cell">{date}</td>'
        f"</tr>"
    )


def render_entry_card(entry: FileEntry, request_path: str) -> str:
    """Render a single file/directory entry as a card (mobile).

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
    icon = _FOLDER_ICON if entry.is_dir else _FILE_ICON
    name_class = "text-karta-700 font-medium" if entry.is_dir else "text-slate-700"

    return (
        f'<a href="{href}" class="flex items-center gap-3 px-4 py-3 '
        f'hover:bg-karta-50/60 transition-colors rounded-lg">'
        f"{icon}"
        f'<div class="min-w-0 flex-1">'
        f'<div class="{name_class} truncate">{name}</div>'
        f'<div class="text-xs text-slate-400 mt-0.5">'
        f"{size} &middot; {date}</div>"
        f"</div>"
        f"{_CHEVRON_ICON}"
        f"</a>"
    )
