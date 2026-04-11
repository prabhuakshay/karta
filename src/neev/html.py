"""HTML page rendering for neev directory listings.

Assembles complete HTML pages using entry renderers from ``html_entries``.
All user-controlled content is escaped via ``html.escape()``.
"""

import html
from pathlib import Path, PurePosixPath

from neev.fs import FileEntry
from neev.html_entries import render_entry_card, render_entry_row
from neev.html_page_template import PAGE_TEMPLATE
from neev.html_upload import render_upload_section


# -- Navigation helpers -------------------------------------------------------

_BACK_ICON = (
    '<svg class="w-4 h-4" fill="none" stroke="currentColor" '
    'viewBox="0 0 24 24"><path stroke-linecap="round" '
    'stroke-linejoin="round" stroke-width="2" '
    'd="M15 19l-7-7 7-7"/></svg>'
)


def _build_breadcrumbs(path: Path, base_dir: Path) -> list[tuple[str, str]]:
    """Build breadcrumb segments from served root to current directory.

    Args:
        path: The current directory being listed (absolute).
        base_dir: The served root directory (absolute).

    Returns:
        List of ``(label, href)`` tuples. The first entry is always the root.
    """
    crumbs: list[tuple[str, str]] = [("~", "/")]

    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        return crumbs

    parts = relative.parts
    if not parts:
        return crumbs

    for i, part in enumerate(parts):
        href = "/" + str(PurePosixPath(*parts[: i + 1])) + "/"
        crumbs.append((part, href))

    return crumbs


def _render_breadcrumb_html(crumbs: list[tuple[str, str]]) -> str:
    """Render breadcrumb navigation as an address-bar style path.

    Args:
        crumbs: List of ``(label, href)`` tuples.

    Returns:
        HTML string for the breadcrumb bar.
    """
    parts: list[str] = []
    last = len(crumbs) - 1

    for i, (label, href) in enumerate(crumbs):
        escaped_label = html.escape(label)
        escaped_href = html.escape(href)

        if i == last:
            parts.append(f'<span class="text-ink-800 font-semibold">{escaped_label}</span>')
        else:
            parts.append(
                f'<a href="{escaped_href}" '
                f'class="text-ink-400 hover:text-sage-500 '
                f'transition-colors duration-150">{escaped_label}</a>'
            )

    sep = (
        '<svg class="w-3.5 h-3.5 text-ink-300 mx-1" '
        'fill="none" stroke="currentColor" viewBox="0 0 24 24">'
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'stroke-width="2" d="M9 5l7 7-7 7"/></svg>'
    )
    return sep.join(parts)


def _parent_link(request_path: str) -> str:
    """Build the parent directory URL.

    Args:
        request_path: The current request URL path.

    Returns:
        URL path to the parent directory.
    """
    stripped = request_path.rstrip("/")
    if "/" not in stripped:
        return "/"
    return stripped.rsplit("/", maxsplit=1)[0] + "/"


def _build_summary(entries: list[FileEntry]) -> str:
    """Build a human-readable summary of directory contents.

    Args:
        entries: List of file entries.

    Returns:
        Summary string like "3 folders, 5 files" or "Empty directory".
    """
    dir_count = sum(1 for e in entries if e.is_dir)
    file_count = len(entries) - dir_count
    parts: list[str] = []
    if dir_count:
        parts.append(f"{dir_count} folder{'s' if dir_count != 1 else ''}")
    if file_count:
        parts.append(f"{file_count} file{'s' if file_count != 1 else ''}")
    return ", ".join(parts) if parts else "Empty directory"


# -- Page assembly ------------------------------------------------------------


def render_directory_listing(
    path: Path,
    entries: list[FileEntry],
    base_dir: Path,
    request_path: str,
    auth_enabled: bool = False,
    enable_zip_download: bool = False,
    enable_upload: bool = False,
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

    Returns:
        Complete HTML page as a string.
    """
    breadcrumb_html = _render_breadcrumb_html(_build_breadcrumbs(path, base_dir))
    is_root = path == base_dir
    parent_href = "" if is_root else html.escape(_parent_link(request_path))
    summary = _build_summary(entries)
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
            f"{_BACK_ICON}"
            f'<span class="text-sm">..</span></a></td></tr>'
        )
        parent_card = (
            f'<a href="{parent_href}" class="flex items-center '
            f"gap-3 px-4 py-3.5 hover:bg-sage-50 "
            f'transition-colors duration-100">'
            f"{_BACK_ICON}"
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
    if enable_zip_download:
        raw = request_path.rstrip("/") + "/?zip" if request_path != "/" else "/?zip"
        zip_href = html.escape(raw)
        zip_html = (
            f'<a href="{zip_href}" class="text-xs text-ink-400'
            " hover:text-sage-500 transition-colors duration-150"
            ' whitespace-nowrap ml-4" title="Download as ZIP">'
            "Download ZIP</a>"
        )

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
    )
