"""HTML page rendering for neev directory listings.

Assembles complete HTML pages using entry renderers from ``html_entries``.
All user-controlled content is escaped via ``html.escape()``.
"""

import html
from pathlib import Path

from neev.fs import FileEntry
from neev.html_entries import render_entry_card, render_entry_row
from neev.html_nav import (
    BACK_ICON,
    build_breadcrumbs,
    build_summary,
    parent_link,
    render_breadcrumb_html,
)
from neev.html_page_template import PAGE_TEMPLATE
from neev.html_upload import render_upload_section


# -- Select bar ---------------------------------------------------------------


def _render_select_bar(zip_href: str) -> str:
    """Render the floating action bar for selective ZIP download.

    Args:
        zip_href: The escaped ZIP download URL.

    Returns:
        HTML string for the fixed-bottom selection bar.
    """
    return (
        '<div x-show="selectMode && selected.length > 0"'
        " x-cloak"
        ' class="fixed bottom-0 left-0 right-0 z-20'
        " bg-surface-1 border-t border-surface-3"
        " shadow-[0_-4px_24px_rgba(0,0,0,0.08)]"
        ' rounded-t-xl">'
        '<div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8'
        ' py-3 flex items-center justify-between gap-3">'
        '<span class="text-sm font-semibold text-ink-700"'
        " x-text=\"selected.length + ' selected'\"></span>"
        '<div class="flex items-center gap-2">'
        # Select All
        '<button type="button" @click="'
        "selected = Array.from("
        "$el.closest('[x-data]')"
        ".querySelectorAll('[data-entry-name]'))"
        ".map(el => el.getAttribute('data-entry-name'))\""
        ' class="px-3 py-1.5 text-sm font-medium text-ink-500'
        " bg-surface-2 rounded-lg hover:bg-surface-3"
        ' transition-colors duration-150">Select All</button>'
        # Download ZIP — call a global helper defined in the page script
        '<button type="button"'
        f" @click=\"submitZip('{zip_href}', selected)\""
        ' class="inline-flex items-center gap-2 px-3.5 py-1.5'
        " text-sm font-semibold text-white bg-sage-500"
        " rounded-lg hover:bg-sage-600 active:bg-sage-700"
        ' transition-colors duration-150">'
        '<svg class="w-4 h-4" fill="none" stroke="currentColor"'
        ' viewBox="0 0 24 24"><path stroke-linecap="round"'
        ' stroke-linejoin="round" stroke-width="2"'
        ' d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4 M7 10l5 5'
        ' 5-5 M12 15V3"/></svg>'
        "Download ZIP</button>"
        # Cancel
        '<button type="button"'
        ' @click="selectMode = false; selected = []"'
        ' class="px-3 py-1.5 text-sm font-medium text-ink-400'
        " hover:text-ink-700 transition-colors"
        ' duration-150">Cancel</button>'
        "</div></div></div>"
    )


# -- Page assembly ------------------------------------------------------------


def render_directory_listing(
    path: Path,
    entries: list[FileEntry],
    base_dir: Path,
    request_path: str,
    auth_enabled: bool = False,
    enable_zip_download: bool = False,
    enable_upload: bool = False,
    banner: str | None = None,
) -> str:
    """Render a complete HTML page for a directory listing.

    Args:
        path: Absolute path to the directory being listed.
        entries: Sorted list of ``FileEntry`` objects.
        base_dir: The served root directory.
        request_path: The original URL path from the request.
        auth_enabled: Whether to show the logout button.
        enable_zip_download: Whether to show the ZIP download link.
        enable_upload: Whether to show the upload and create-folder forms.
        banner: Optional message to display at the top of the listing.

    Returns:
        Complete HTML page as a string.
    """
    breadcrumb_html = render_breadcrumb_html(build_breadcrumbs(path, base_dir))
    is_root = path == base_dir
    parent_href = "" if is_root else html.escape(parent_link(request_path))
    summary = build_summary(entries)
    dir_name = html.escape(path.name or "/")

    parent_row = ""
    parent_card = ""
    if not is_root:
        parent_row = (
            f'<tr class="hover:bg-sage-50 '
            f'transition-colors duration-100">'
            f'<td class="px-4 py-3" colspan="3">'
            f'<a href="{parent_href}" class="flex items-center '
            f"gap-3 text-ink-400 hover:text-sage-500 "
            f'transition-colors duration-150">'
            f"{BACK_ICON}"
            f'<span class="text-sm">..</span></a></td></tr>'
        )
        parent_card = (
            f'<a href="{parent_href}" class="flex items-center '
            f"gap-3 px-4 py-3.5 hover:bg-sage-50 "
            f'transition-colors duration-100">'
            f"{BACK_ICON}"
            f'<span class="text-ink-400 text-sm">..</span>'
            f"</a>"
        )

    table_rows = parent_row + "".join(render_entry_row(e, request_path) for e in entries)
    card_items = parent_card + "".join(render_entry_card(e, request_path) for e in entries)

    empty_state = ""
    if not entries:
        empty_state = (
            '<div class="text-center py-20">'
            '<div class="w-16 h-16 rounded-xl bg-surface-2 '
            'flex items-center justify-center mx-auto mb-4">'
            '<svg class="w-8 h-8 text-ink-300" fill="none" '
            'stroke="currentColor" viewBox="0 0 24 24">'
            '<path stroke-linecap="round" stroke-linejoin="round" '
            'stroke-width="1.5" d="M3 7v10a2 2 0 002 2h14a2 2 0 '
            '002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/>'
            "</svg></div>"
            '<p class="text-ink-500 text-sm font-medium">'
            "Nothing here yet</p>"
            '<p class="text-ink-300 text-xs mt-1">'
            "This directory is empty</p></div>"
        )

    zip_html = ""
    select_bar_html = ""
    if enable_zip_download:
        raw = request_path.rstrip("/") + "/?zip" if request_path != "/" else "/?zip"
        zip_href = html.escape(raw)
        zip_html = (
            f'<a href="{zip_href}" class="inline-flex items-center gap-2'
            " px-3.5 py-2 bg-surface-1 text-ink-700 text-sm font-semibold"
            " rounded-lg border border-surface-3 hover:bg-surface-2"
            " hover:border-surface-4 hover:shadow-sm"
            " active:bg-surface-3 transition-all duration-150"
            ' whitespace-nowrap" title="Download as ZIP">'
            '<svg class="w-4 h-4" fill="none" stroke="currentColor"'
            ' viewBox="0 0 24 24"><path stroke-linecap="round"'
            ' stroke-linejoin="round" stroke-width="2"'
            ' d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4 M7 10l5 5'
            ' 5-5 M12 15V3"/></svg>'
            "Download ZIP</a>"
            '<button @click="selectMode = !selectMode;'
            ' if (!selectMode) selected = []"'
            ' :class="selectMode'
            " ? 'bg-sage-500 text-white border-sage-500"
            " hover:bg-sage-600 active:bg-sage-700'"
            " : 'bg-surface-1 text-ink-700 border-surface-3"
            " hover:bg-surface-2 active:bg-surface-3'\""
            ' class="inline-flex items-center gap-2 px-3.5 py-2'
            " text-sm font-semibold rounded-lg border cursor-pointer"
            ' transition-all duration-150 whitespace-nowrap"'
            ' title="Select files">'
            '<svg class="w-4 h-4" fill="none" stroke="currentColor"'
            ' viewBox="0 0 24 24"><path stroke-linecap="round"'
            ' stroke-linejoin="round" stroke-width="2"'
            ' d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7'
            " a2 2 0 00-2-2h-2 M9 5a2 2 0 002 2h2a2 2 0 002-2"
            ' M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>'
            '<span class="hidden sm:inline">Select</span></button>'
        )
        select_bar_html = _render_select_bar(zip_href)

    logout_html = ""
    if auth_enabled:
        logout_html = (
            '<a href="/_neev/logout" class="text-xs text-ink-400'
            " hover:text-sage-500 transition-colors duration-150"
            ' whitespace-nowrap ml-4" title="Sign out">Sign out</a>'
        )

    upload_html = ""
    if enable_upload:
        upload_html = render_upload_section(request_path)

    banner_html = ""
    if banner:
        banner_html = (
            '<div class="mb-4 px-4 py-3 bg-sage-50 border border-sage-200'
            ' rounded-lg flex items-center gap-3">'
            '<svg class="w-4 h-4 text-sage-500 shrink-0" fill="none"'
            ' stroke="currentColor" viewBox="0 0 24 24">'
            '<path stroke-linecap="round" stroke-linejoin="round"'
            ' stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01'
            ' M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'
            f'<p class="text-sm text-sage-700">{html.escape(banner)}</p>'
            "</div>"
        )

    return PAGE_TEMPLATE.format(
        dir_name=dir_name,
        breadcrumb_html=breadcrumb_html,
        summary=summary,
        zip_html=zip_html,
        logout_html=logout_html,
        table_rows=table_rows,
        card_items=card_items,
        empty_state=empty_state,
        upload_html=upload_html,
        banner_html=banner_html,
        select_bar_html=select_bar_html,
    )
