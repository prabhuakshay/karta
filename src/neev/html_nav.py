"""Navigation helpers for neev directory listings.

Breadcrumb generation, parent link resolution, and directory summaries.
All user-controlled content is escaped via ``html.escape()``.
"""

import html
from pathlib import Path, PurePosixPath

from neev.fs import FileEntry


BACK_ICON = (
    '<svg class="w-4 h-4" aria-hidden="true" fill="none" stroke="currentColor" '
    'viewBox="0 0 24 24"><path stroke-linecap="round" '
    'stroke-linejoin="round" stroke-width="2" '
    'd="M15 19l-7-7 7-7"/></svg>'
)


def build_breadcrumbs(path: Path, base_dir: Path) -> list[tuple[str, str]]:
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


def render_breadcrumb_html(crumbs: list[tuple[str, str]]) -> str:
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
        '<svg class="w-3.5 h-3.5 text-ink-300 mx-1" aria-hidden="true" '
        'fill="none" stroke="currentColor" viewBox="0 0 24 24">'
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'stroke-width="2" d="M9 5l7 7-7 7"/></svg>'
    )
    return sep.join(parts)


def parent_link(request_path: str) -> str:
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


def build_summary(entries: list[FileEntry]) -> str:
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
