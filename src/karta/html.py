"""HTML page rendering for karta directory listings.

Assembles complete HTML pages using entry renderers from ``html_entries``.
All user-controlled content is escaped via ``html.escape()``.
"""

import html
from pathlib import Path, PurePosixPath

from karta.fs import FileEntry
from karta.html_entries import render_entry_card, render_entry_row


# -- Navigation helpers -------------------------------------------------------

_BACK_ARROW = (
    '<svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" '
    'viewBox="0 0 24 24"><path stroke-linecap="round" '
    'stroke-linejoin="round" stroke-width="2" d="M11 17l-5-5m0 '
    '0l5-5m-5 5h12"/></svg>'
)


def _build_breadcrumbs(path: Path, base_dir: Path) -> list[tuple[str, str]]:
    """Build breadcrumb segments from served root to current directory.

    Args:
        path: The current directory being listed (absolute).
        base_dir: The served root directory (absolute).

    Returns:
        List of ``(label, href)`` tuples. The first entry is always the root.
    """
    crumbs: list[tuple[str, str]] = [("\u2302", "/")]

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
    """Render breadcrumb navigation as HTML.

    Args:
        crumbs: List of ``(label, href)`` tuples from ``_build_breadcrumbs``.

    Returns:
        HTML string for the breadcrumb bar.
    """
    parts: list[str] = []
    last = len(crumbs) - 1

    for i, (label, href) in enumerate(crumbs):
        escaped_label = html.escape(label)
        escaped_href = html.escape(href)

        if i == last:
            parts.append(f'<span class="text-slate-700 font-semibold">{escaped_label}</span>')
        else:
            parts.append(
                f'<a href="{escaped_href}" '
                f'class="text-karta-600 hover:text-karta-800 '
                f'hover:underline transition-colors">'
                f"{escaped_label}</a>"
            )

    separator = '<span class="text-slate-300 mx-1.5">/</span>'
    return separator.join(parts)


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

_FILTER_SCRIPT = """<script>
  document.addEventListener('alpine:init', () => {
    Alpine.effect(() => {
      const root = document.querySelector('[x-data]');
      if (!root) return;
      const filter = Alpine.$data(root).filter.toLowerCase();
      document.querySelectorAll('tbody tr').forEach(row => {
        const name = row.querySelector('span.truncate');
        if (!name) { row.style.display = ''; return; }
        row.style.display = name.textContent.toLowerCase().includes(filter) ? '' : 'none';
      });
      document.querySelectorAll('.sm\\\\:hidden > a').forEach(card => {
        const name = card.querySelector('.truncate');
        if (!name) { card.style.display = ''; return; }
        card.style.display = name.textContent.toLowerCase().includes(filter) ? '' : 'none';
      });
    });
  });
</script>"""


def render_directory_listing(
    path: Path,
    entries: list[FileEntry],
    base_dir: Path,
    request_path: str,
) -> str:
    """Render a complete HTML page for a directory listing.

    Args:
        path: Absolute path to the directory being listed.
        entries: Sorted list of ``FileEntry`` objects from ``fs.list_directory``.
        base_dir: The served root directory.
        request_path: The original URL path from the request.

    Returns:
        Complete HTML page as a string.
    """
    breadcrumb_html = _render_breadcrumb_html(_build_breadcrumbs(path, base_dir))
    is_root = path == base_dir
    parent_href = "" if is_root else html.escape(_parent_link(request_path))
    summary = _build_summary(entries)
    dir_name = html.escape(path.name or "/")

    # Parent directory row/card for non-root directories
    parent_row = ""
    parent_card = ""
    if not is_root:
        parent_row = (
            f'<tr class="group hover:bg-karta-50/60 transition-colors">'
            f'<td class="py-2.5 pl-4 pr-2" colspan="3">'
            f'<a href="{parent_href}" class="flex items-center gap-2.5 '
            f'text-slate-500 hover:text-karta-600 transition-colors">'
            f"{_BACK_ARROW}"
            f"<span>..</span></a></td></tr>"
        )
        parent_card = (
            f'<a href="{parent_href}" class="flex items-center gap-3 px-4 '
            f'py-3 hover:bg-karta-50/60 transition-colors rounded-lg">'
            f'<svg class="w-5 h-5 text-slate-400 shrink-0" fill="none" '
            f'stroke="currentColor" viewBox="0 0 24 24"><path '
            f'stroke-linecap="round" stroke-linejoin="round" '
            f'stroke-width="2" d="M11 17l-5-5m0 0l5-5m-5 5h12"/></svg>'
            f'<div class="text-slate-500">..</div></a>'
        )

    table_rows = parent_row + "".join(render_entry_row(e, request_path) for e in entries)
    card_items = parent_card + "".join(render_entry_card(e, request_path) for e in entries)

    empty_state = ""
    if not entries:
        empty_state = (
            '<div class="text-center py-16">'
            '<svg class="w-12 h-12 text-slate-300 mx-auto mb-4" fill="none" '
            'stroke="currentColor" viewBox="0 0 24 24">'
            '<path stroke-linecap="round" stroke-linejoin="round" '
            'stroke-width="1.5" d="M3 7v10a2 2 0 002 2h14a2 2 0 '
            '002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/></svg>'
            '<p class="text-slate-400 text-sm">This directory is empty</p>'
            "</div>"
        )

    return _PAGE_TEMPLATE.format(
        dir_name=dir_name,
        breadcrumb_html=breadcrumb_html,
        summary=summary,
        table_rows=table_rows,
        card_items=card_items,
        empty_state=empty_state,
        filter_script=_FILTER_SCRIPT,
    )


_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{dir_name} &mdash; karta</title>
  <link rel="icon" href="/favicon.ico" type="image/svg+xml">
  <link rel="stylesheet" href="/_karta/static/karta.css">
  <script defer src="/_karta/static/alpine.min.js"></script>
</head>
<body class="bg-slate-50 min-h-screen">
  <header class="bg-white border-b border-slate-200 sticky top-0 z-10">
    <div class="max-w-5xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="w-8 h-8 rounded-lg bg-karta-600 flex items-center justify-center">
          <span class="text-white font-bold text-sm">K</span>
        </div>
        <nav class="text-sm flex items-center flex-wrap">{breadcrumb_html}</nav>
      </div>
      <div class="text-xs text-slate-400">{summary}</div>
    </div>
  </header>
  <main class="max-w-5xl mx-auto px-4 sm:px-6 py-6">
    <div x-data="{{ filter: '' }}" class="space-y-4">
      <div class="relative">
        <svg class="absolute left-3 top-1/2 -translate-y-1/2
          w-4 h-4 text-slate-400" fill="none"
          stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round"
            stroke-width="2"
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
        </svg>
        <input x-model="filter" type="text"
          placeholder="Filter files&hellip;"
          class="w-full pl-10 pr-4 py-2.5 bg-white border
            border-slate-200 rounded-xl text-sm text-slate-700
            placeholder-slate-400 focus:outline-none focus:ring-2
            focus:ring-karta-500/20 focus:border-karta-400
            transition">
      </div>
      <div class="hidden sm:block bg-white rounded-xl
        border border-slate-200 overflow-hidden shadow-sm">
        <table class="w-full">
          <thead>
            <tr class="border-b border-slate-100 text-xs
              text-slate-400 uppercase tracking-wider">
              <th class="py-2.5 pl-4 pr-2 text-left
                font-medium">Name</th>
              <th class="py-2.5 px-3 text-right font-medium
                hidden sm:table-cell">Size</th>
              <th class="py-2.5 px-3 pr-4 text-right font-medium
                hidden md:table-cell">Modified</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-50">
            {table_rows}
          </tbody>
        </table>
      </div>
      <div class="sm:hidden bg-white rounded-xl border
        border-slate-200 overflow-hidden shadow-sm
        divide-y divide-slate-100">
        {card_items}
      </div>
    </div>
    {empty_state}
  </main>
  <footer class="max-w-5xl mx-auto px-4 sm:px-6 py-6 text-center">
    <p class="text-xs text-slate-300">served by karta</p>
  </footer>
  {filter_script}
</body>
</html>"""
