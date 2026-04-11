"""HTML page rendering for karta directory listings.

Assembles complete HTML pages using entry renderers from ``html_entries``.
All user-controlled content is escaped via ``html.escape()``.
"""

import html
from pathlib import Path, PurePosixPath

from karta.fs import FileEntry
from karta.html_entries import render_entry_card, render_entry_row
from karta.html_upload import render_upload_section


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
            '<a href="/_karta/logout" class="text-xs text-ink-400'
            " hover:text-sage-500 transition-colors duration-150"
            ' whitespace-nowrap ml-4" title="Sign out">Sign out</a>'
        )

    upload_html = ""
    if enable_upload:
        upload_html = render_upload_section(request_path)

    return _PAGE_TEMPLATE.format(
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


_PAGE_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en" class="antialiased">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{dir_name} &mdash; karta</title>
  <link rel="icon" href="/favicon.ico" type="image/svg+xml">
  <link rel="stylesheet" href="/_karta/static/karta.css">
  <script defer src="/_karta/static/alpine.min.js"></script>
</head>
<body class="bg-surface-0 text-ink-700 font-sans min-h-screen
  flex flex-col">

  <header class="bg-surface-1/80 backdrop-blur-lg border-b
    border-surface-3 sticky top-0 z-10">
    <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8
      h-14 flex items-center justify-between">
      <div class="flex items-center gap-3 min-w-0">
        <a href="/" class="flex items-center gap-2 shrink-0
          group" title="karta root">
          <div class="w-7 h-7 rounded-lg bg-gradient-to-br
            from-sage-400 to-sage-600 flex items-center
            justify-center shadow-card
            group-hover:shadow-card-md transition-shadow
            duration-200">
            <span class="text-white font-bold
              text-xs leading-none">K</span>
          </div>
        </a>
        <nav class="flex items-center text-sm min-w-0
          overflow-x-auto scrollbar-none">
          {breadcrumb_html}
        </nav>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-xs text-ink-400 tabular-nums
          whitespace-nowrap hidden sm:block">
          {summary}
        </span>
        {zip_html}
        {logout_html}
      </div>
    </div>
  </header>

  <main class="max-w-5xl mx-auto w-full px-4 sm:px-6
    lg:px-8 py-5 flex-1"
    x-data="{{ filter: '' }}"
    x-effect="
      const f = filter.toLowerCase();
      $el.querySelectorAll('tbody tr').forEach(r => {{
        const n = r.querySelector('.truncate');
        if (!n) {{ r.style.display = ''; return; }}
        r.style.display =
          n.textContent.toLowerCase().includes(f)
            ? '' : 'none';
      }});
      $el.querySelectorAll(
        '.mobile-list > a'
      ).forEach(c => {{
        const n = c.querySelector('.truncate');
        if (!n) {{ c.style.display = ''; return; }}
        c.style.display =
          n.textContent.toLowerCase().includes(f)
            ? '' : 'none';
      }});
    ">

    <div class="relative mb-4">
      <svg class="absolute left-3.5 top-1/2
        -translate-y-1/2 w-4 h-4 text-ink-300
        pointer-events-none" fill="none"
        stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round"
          stroke-linejoin="round" stroke-width="2"
          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
      </svg>
      <input x-model="filter" type="text"
        placeholder="Filter&hellip;"
        class="w-full sm:w-72 pl-10 pr-4 py-2.5
          bg-surface-2 border border-surface-3
          rounded-md text-sm text-ink-700
          placeholder:text-ink-300
          hover:border-surface-4
          focus:border-sage-400 focus:bg-surface-1
          focus:ring-2 focus:ring-sage-50
          transition-colors duration-150">
    </div>

    <div class="hidden sm:block bg-surface-1
      shadow-card rounded-xl overflow-hidden">
      <table class="w-full">
        <thead class="bg-surface-2/40">
          <tr class="border-b border-surface-3">
            <th class="py-3 px-4 text-left text-label
              uppercase tracking-wider text-ink-400
              font-semibold">Name</th>
            <th class="py-3 px-4 text-right text-label
              uppercase tracking-wider text-ink-400
              font-semibold hidden sm:table-cell">Size</th>
            <th class="py-3 px-4 text-right text-label
              uppercase tracking-wider text-ink-400
              font-semibold hidden md:table-cell">Modified</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-surface-3">
          {table_rows}
        </tbody>
      </table>
    </div>

    <div class="sm:hidden bg-surface-1 shadow-card
      rounded-xl overflow-hidden mobile-list
      divide-y divide-surface-3">
      {card_items}
    </div>

    {empty_state}

    {upload_html}
  </main>

  <footer class="max-w-5xl mx-auto w-full px-4 sm:px-6
    lg:px-8 py-4">
    <p class="text-xs text-ink-300 text-center
      tracking-wide">
      served by
      <span class="font-medium text-ink-400">karta</span>
    </p>
  </footer>
</body>
</html>"""
