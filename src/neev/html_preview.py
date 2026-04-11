"""HTML templates for inline file preview pages (images, text, PDF)."""

import html


_PREVIEW_HEADER = """\
<!DOCTYPE html>
<html lang="en" class="antialiased">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{filename} &mdash; neev</title>
  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/_neev/static/neev.css">
</head>
<body class="bg-surface-0 text-ink-700 font-sans min-h-screen
  flex flex-col">

  <header class="bg-surface-1/80 backdrop-blur-lg border-b
    border-surface-3 sticky top-0 z-10">
    <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8
      h-14 flex items-center justify-between">
      <div class="flex items-center gap-3 min-w-0">
        <a href="{parent_url}" class="flex items-center gap-2
          text-ink-400 hover:text-sage-500 transition-colors
          duration-150 shrink-0" title="Back to folder">
          <svg class="w-4 h-4" fill="none" stroke="currentColor"
            viewBox="0 0 24 24"><path stroke-linecap="round"
            stroke-linejoin="round" stroke-width="2"
            d="M15 19l-7-7 7-7"/></svg>
        </a>
        <span class="text-sm text-ink-800 font-semibold
          truncate">{filename}</span>
      </div>
      <a href="{download_url}"
        class="inline-flex items-center gap-2
          px-3.5 py-2 bg-surface-1 text-ink-700 text-sm
          font-semibold rounded-lg border border-surface-3
          hover:bg-surface-2 active:bg-surface-3
          transition-colors duration-150 whitespace-nowrap">
        <svg class="w-4 h-4" fill="none"
          stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round"
            stroke-width="2"
            d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4
              M7 10l5 5 5-5 M12 15V3"/>
        </svg>
        <span class="hidden sm:inline">Download</span>
      </a>
    </div>
  </header>

  <main class="max-w-5xl mx-auto w-full px-4 sm:px-6
    lg:px-8 py-8 flex-1">"""

_PREVIEW_FOOTER = """\
  </main>

  <footer class="max-w-5xl mx-auto w-full px-4 sm:px-6
    lg:px-8 py-4">
    <p class="text-xs text-ink-300 text-center tracking-wide">
      served by
      <span class="font-medium text-ink-400">neev</span>
    </p>
  </footer>
</body>
</html>"""


def _header(filename: str, parent_url: str, download_url: str) -> str:
    return _PREVIEW_HEADER.format(
        filename=filename,
        parent_url=parent_url,
        download_url=download_url,
    )


def render_image_preview(filename: str, raw_url: str, parent_url: str, download_url: str) -> str:
    """Render a preview page for an image file.

    Args:
        filename: Display name of the file (pre-escaped).
        raw_url: URL to the raw image file (pre-escaped).
        parent_url: URL of the parent directory (pre-escaped).
        download_url: URL for forced download (pre-escaped).

    Returns:
        Complete HTML page as a string.
    """
    return (
        f"{_header(filename, parent_url, download_url)}"
        f'    <div class="bg-surface-1 shadow-card rounded-xl p-4'
        f' sm:p-8 flex items-center justify-center">'
        f'      <img src="{raw_url}" alt="{filename}"'
        f' class="max-w-full max-h-[80vh] rounded-lg object-contain">'
        f"    </div>"
        f"{_PREVIEW_FOOTER}"
    )


def render_text_preview(filename: str, raw_url_js: str, parent_url: str, download_url: str) -> str:
    """Render a preview page for a text/code file with syntax highlighting.

    Args:
        filename: Display name of the file (pre-escaped for HTML).
        raw_url_js: URL to the raw file content (JSON-encoded string literal).
        parent_url: URL of the parent directory (pre-escaped for HTML).
        download_url: URL for forced download (pre-escaped for HTML).

    Returns:
        Complete HTML page as a string.
    """
    return (
        f"{_header(filename, parent_url, download_url)}"
        '    <link rel="stylesheet"'
        ' href="https://cdn.jsdelivr.net/gh/highlightjs/'
        'cdn-release/build/styles/github.min.css">'
        '    <div class="bg-surface-1 shadow-card rounded-xl overflow-hidden">'
        '      <pre id="code-content"'
        ' class="p-6 sm:p-10 text-sm text-ink-700 font-mono'
        " leading-relaxed overflow-x-auto whitespace-pre-wrap"
        ' break-words"><span class="text-ink-400">Loading\u2026</span></pre>'
        "    </div>"
        '    <script defer src="https://cdn.jsdelivr.net/gh/highlightjs/'
        'cdn-release/build/highlight.min.js"></script>'
        "    <script>"
        f"    fetch({raw_url_js})"
        "      .then(function(r) { return r.text(); })"
        "      .then(function(text) {"
        "        var el = document.getElementById('code-content');"
        "        el.textContent = text;"
        "        if (window.hljs) hljs.highlightElement(el);"
        "      });"
        "    </script>"
        f"{_PREVIEW_FOOTER}"
    )


def render_pdf_preview(filename: str, raw_url: str, parent_url: str, download_url: str) -> str:
    """Render a preview page for a PDF file.

    Args:
        filename: Display name of the file (pre-escaped).
        raw_url: URL to the raw PDF file (pre-escaped).
        parent_url: URL of the parent directory (pre-escaped).
        download_url: URL for forced download (pre-escaped).

    Returns:
        Complete HTML page as a string.
    """
    return (
        f"{_header(filename, parent_url, download_url)}"
        f'    <div class="bg-surface-1 shadow-card rounded-xl'
        f' overflow-hidden" style="height:85vh">'
        f'      <embed src="{raw_url}" type="application/pdf"'
        f' class="w-full h-full">'
        f"    </div>"
        f"{_PREVIEW_FOOTER}"
    )


def render_media_preview(
    filename: str,
    raw_url: str,
    parent_url: str,
    download_url: str,
    mime_type: str,
) -> str:
    """Render a preview page for a video or audio file.

    Args:
        filename: Display name of the file (pre-escaped).
        raw_url: URL to the raw media file (pre-escaped).
        parent_url: URL of the parent directory (pre-escaped).
        download_url: URL for forced download (pre-escaped).
        mime_type: The MIME type (e.g. ``video/mp4``).

    Returns:
        Complete HTML page as a string.
    """
    tag = "video" if mime_type.startswith("video/") else "audio"
    extra = ' class="max-w-full max-h-[80vh] rounded-lg"' if tag == "video" else ""
    return (
        f"{_header(filename, parent_url, download_url)}"
        f'    <div class="bg-surface-1 shadow-card rounded-xl p-4'
        f' sm:p-8 flex items-center justify-center">'
        f"      <{tag} controls{extra}>"
        f'        <source src="{raw_url}" type="{html.escape(mime_type)}">'
        f"      </{tag}>"
        f"    </div>"
        f"{_PREVIEW_FOOTER}"
    )
