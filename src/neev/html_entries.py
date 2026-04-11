"""HTML rendering for individual file/directory entries.

Handles table rows (desktop), cards (mobile) for directory listings.
File-type-aware icons with Lumina color coding.
Display text is escaped via ``html.escape()``; hrefs use ``urllib.parse.quote``.
"""

import html
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from neev.fs import FileEntry, get_mime_type, is_markdown_file, is_previewable_type
from neev.html_icons import icon_for_entry


_COPY_ICON = (
    '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor"'
    ' viewBox="0 0 24 24"><path stroke-linecap="round"'
    ' stroke-linejoin="round" stroke-width="2"'
    ' d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2'
    " m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8"
    ' a2 2 0 002 2z"/></svg>'
)

_CHECK_ICON = (
    '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor"'
    ' viewBox="0 0 24 24"><path stroke-linecap="round"'
    ' stroke-linejoin="round" stroke-width="2"'
    ' d="M5 13l4 4L19 7"/></svg>'
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
    name = quote(entry.name, safe="")
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


def _file_data_attrs(entry: FileEntry, href: str) -> str:
    """Build extra HTML attributes for file entry links.

    Adds ``data-href`` for all files (used by the download-mode toggle)
    and ``data-preview-href`` for previewable files (markdown, images,
    text, PDF, audio, video).

    Args:
        entry: The file entry.
        href: The already-quoted href for this entry.

    Returns:
        A string of HTML attributes (with leading space), or empty for dirs.
    """
    if entry.is_dir:
        return ""
    preview = ""
    if is_markdown_file(PurePosixPath(entry.name)) or is_previewable_type(
        get_mime_type(Path(entry.name))
    ):
        preview = f' data-preview-href="{href}?preview"'
    return f' data-href="{href}"{preview}'


def _copy_link_button(href: str) -> str:
    """Render a copy-link button for a file entry.

    Args:
        href: The URL-safe href for this file.

    Returns:
        HTML button string with Alpine.js click handler.
    """
    return (
        f"<button @click.prevent.stop=\"copyLink($event, '{href}')\""
        ' class="copy-link-btn ml-1 p-1 rounded text-ink-300'
        " hover:text-sage-500 hover:bg-sage-50"
        " opacity-0 group-hover:opacity-100"
        " focus:opacity-100 cursor-pointer"
        ' transition-all duration-150"'
        ' title="Copy link" type="button">'
        f'<span class="icon-copy">{_COPY_ICON}</span>'
        f'<span class="icon-check" style="display:none">{_CHECK_ICON}</span>'
        "</button>"
    )


def _copy_link_button_mobile(href: str) -> str:
    """Render a copy-link button for a mobile file card.

    Args:
        href: The URL-safe href for this file.

    Returns:
        HTML button string, always visible on mobile.
    """
    return (
        f"<button @click.prevent.stop=\"copyLink($event, '{href}')\""
        ' class="copy-link-btn p-1.5 rounded text-ink-300'
        " hover:text-sage-500 hover:bg-sage-50 cursor-pointer"
        ' transition-all duration-150 shrink-0"'
        ' title="Copy link" type="button">'
        f'<span class="icon-copy">{_COPY_ICON}</span>'
        f'<span class="icon-check" style="display:none">{_CHECK_ICON}</span>'
        "</button>"
    )


def _js_escape(value: str) -> str:
    """Escape a string for safe use inside JavaScript single-quoted literals.

    Args:
        value: The raw string to escape.

    Returns:
        String with backslashes and single quotes escaped.
    """
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _entry_checkbox(html_name: str, js_name_attr: str) -> str:
    """Render a select-mode checkbox for a directory entry.

    Args:
        html_name: HTML-escaped entry name (for value/data attributes).
        js_name_attr: JS-escaped then HTML-escaped name (for Alpine attributes).

    Returns:
        HTML checkbox input string.
    """
    return (
        f'<input type="checkbox" value="{html_name}"'
        f' aria-label="Select {html_name}"'
        ' x-show="selectMode"'
        f" @click.stop=\"toggleItem('{js_name_attr}')\""
        f" :checked=\"isSelected('{js_name_attr}')\""
        ' class="w-4 h-4 rounded border-surface-4'
        ' accent-sage-500 cursor-pointer shrink-0"'
        f' data-entry-name="{html_name}">'
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
    icon_html = icon_for_entry(entry.name, entry.is_dir)
    badge = "" if entry.is_dir else _ext_badge(entry.name)
    name_cls = "text-ink-800 font-medium" if entry.is_dir else "text-ink-700"

    data_attrs = _file_data_attrs(entry, href)
    copy_btn = "" if entry.is_dir else _copy_link_button(href)
    js_name_attr = html.escape(_js_escape(entry.name))
    checkbox = _entry_checkbox(name, js_name_attr)

    return (
        f'<tr class="group hover:bg-sage-50 '
        f'transition-colors duration-100"'
        f' @click="if (selectMode) {{ $event.preventDefault();'
        f" toggleItem('{js_name_attr}'); }}\""
        f" :class=\"isSelected('{js_name_attr}') ? 'bg-sage-50' : ''\">"
        f'<td class="px-4 py-3">'
        f'<div class="flex items-center gap-3">'
        f"{checkbox}"
        f'<a href="{href}"{data_attrs}'
        f' class="{"file-link " if not entry.is_dir else ""}'
        f"flex items-center gap-3 min-w-0 "
        f"{name_cls} group-hover:text-sage-500 "
        f'transition-colors duration-150">'
        f"{icon_html}"
        f'<span class="truncate text-sm">{name}</span>{badge}'
        f"</a>{copy_btn}</div></td>"
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
    icon_html = icon_for_entry(entry.name, entry.is_dir)
    name_cls = "text-ink-800 font-medium" if entry.is_dir else "text-ink-700"
    data_attrs = _file_data_attrs(entry, href)

    chevron = (
        '<svg class="w-4 h-4 text-ink-300 shrink-0" fill="none" '
        'stroke="currentColor" viewBox="0 0 24 24">'
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'stroke-width="2" d="M9 5l7 7-7 7"/></svg>'
    )
    copy_btn = _copy_link_button_mobile(href) if not entry.is_dir else ""
    trailing = copy_btn + chevron if copy_btn else chevron

    js_name_attr = html.escape(_js_escape(entry.name))
    checkbox_mobile = _entry_checkbox(name, js_name_attr)

    return (
        f'<a href="{href}"{data_attrs}'
        f' class="{"file-link " if not entry.is_dir else ""}'
        f"flex items-center gap-3 "
        f"px-4 py-3.5 hover:bg-sage-50 "
        f'transition-colors duration-100"'
        f' @click="if (selectMode) {{ $event.preventDefault();'
        f" toggleItem('{js_name_attr}'); }}\""
        f" :class=\"isSelected('{js_name_attr}') ? 'bg-sage-50' : ''\">"
        f"{checkbox_mobile}"
        f"{icon_html}"
        f'<div class="min-w-0 flex-1">'
        f'<div class="{name_cls} truncate text-sm">{name}</div>'
        f'<div class="text-xs text-ink-400 mt-0.5">'
        f"{size} &middot; {date}</div>"
        f"</div>"
        f"{trailing}"
        f"</a>"
    )
