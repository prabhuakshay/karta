"""HTML template for markdown file preview with Mermaid diagram support."""

from string import Template

from neev.html_markdown_assets import MARKDOWN_CSS, MARKDOWN_JS


_MARKDOWN_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en" class="antialiased">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>$filename &mdash; neev</title>
  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/_neev/static/neev.css">
  <script defer src="https://cdn.jsdelivr.net/npm/marked@15.0.12/marked.min.js"
    integrity="sha384-948ahk4ZmxYVYOc+rxN1H2gM1EJ2Duhp7uHtZ4WSLkV4Vtx5MUqnV+l7u9B+jFv+"
    crossorigin="anonymous"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/mermaid@11.14.0/dist/mermaid.min.js"
    integrity="sha384-1CMXl090wj8Dd6YfnzSQUOgWbE6suWCaenYG7pox5AX7apTpY3PmJMeS2oPql4Gk"
    crossorigin="anonymous"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/dompurify@3.3.3/dist/purify.min.js"
    integrity="sha384-pcBjnGbkyKeOXaoFkmJiuR9E08/6gkmus6/Strimnxtl3uk0Hx23v345pWyC/MMr"
    crossorigin="anonymous"></script>
  <link rel="stylesheet"
    href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/styles/github.min.css"
    integrity="sha384-eFTL69TLRZTkNfYZOLM+G04821K1qZao/4QLJbet1pP4tcF+fdXq/9CdqAbWRl/L"
    crossorigin="anonymous">
  <script defer
    src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/highlight.min.js"
    integrity="sha384-RH2xi4eIQ/gjtbs9fUXM68sLSi99C7ZWBRX1vDrVv6GQXRibxXLbwO2NGZB74MbU"
    crossorigin="anonymous"></script>
  <style>
$css
  </style>
</head>
<body class="bg-surface-0 text-ink-700 font-sans min-h-screen
  flex flex-col">

  <header class="bg-surface-1/80 backdrop-blur-lg border-b
    border-surface-3 sticky top-0 z-10">
    <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8
      h-14 flex items-center justify-between">
      <div class="flex items-center gap-3 min-w-0">
        <a href="$parent_url" class="flex items-center gap-2
          text-ink-400 hover:text-sage-500 transition-colors
          duration-150 shrink-0" title="Back to folder">
          <svg class="w-4 h-4" aria-hidden="true" fill="none"
            stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round"
            stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
        </a>
        <span class="text-sm text-ink-800 font-semibold
          truncate">$filename</span>
      </div>
      <div class="flex items-center gap-2">
        <button id="raw-toggle"
          class="inline-flex items-center gap-2
            px-3.5 py-2 bg-surface-1 text-ink-700 text-sm
            font-semibold rounded-lg border border-surface-3
            hover:bg-surface-2 active:bg-surface-3
            transition-colors duration-150 whitespace-nowrap">
          <svg class="w-4 h-4" aria-hidden="true" fill="none"
            stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round"
              stroke-width="2"
              d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/>
          </svg>
          <span class="hidden sm:inline">Raw</span>
        </button>
        <a href="$raw_url"
          class="inline-flex items-center gap-2
            px-3.5 py-2 bg-surface-1 text-ink-700 text-sm
            font-semibold rounded-lg border border-surface-3
            hover:bg-surface-2 active:bg-surface-3
            transition-colors duration-150 whitespace-nowrap">
          <svg class="w-4 h-4" aria-hidden="true" fill="none"
            stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round"
              stroke-width="2"
              d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4
                M7 10l5 5 5-5 M12 15V3"/>
          </svg>
          <span class="hidden sm:inline">Download</span>
        </a>
      </div>
    </div>
  </header>

  <main class="max-w-4xl mx-auto w-full px-4 sm:px-6
    lg:px-8 py-8 flex-1">
    <div id="rendered" class="bg-surface-1 shadow-card
      rounded-xl p-6 sm:p-10">
      <div class="md-body" id="md-content">
        <div class="flex items-center justify-center py-16">
          <div class="w-6 h-6 border-2 border-sage-400
            border-t-transparent rounded-full animate-spin">
          </div>
          <span class="ml-3 text-sm text-ink-400">
            Loading&hellip;</span>
        </div>
      </div>
    </div>
    <div id="raw-view" class="bg-surface-1 shadow-card
      rounded-xl overflow-hidden hidden">
      <pre id="raw-content"
        class="p-6 sm:p-10 text-sm text-ink-700 font-mono
          leading-relaxed overflow-x-auto whitespace-pre-wrap
          break-words"></pre>
    </div>
  </main>

  <footer class="max-w-4xl mx-auto w-full px-4 sm:px-6
    lg:px-8 py-4">
    <p class="text-xs text-ink-300 text-center tracking-wide">
      served by
      <span class="font-medium text-ink-400">neev</span>
    </p>
  </footer>

  <script>
$js
  </script>
</body>
</html>"""


def render_markdown_preview(filename: str, raw_url: str, raw_url_js: str, parent_url: str) -> str:
    """Render an HTML page that previews a markdown file.

    Args:
        filename: Display name of the markdown file (pre-escaped for HTML).
        raw_url: URL for the download link (pre-escaped for HTML attributes).
        raw_url_js: URL to fetch raw markdown (JSON-encoded string literal).
        parent_url: URL of the parent directory (pre-escaped for HTML).

    Returns:
        Complete HTML page as a string.
    """
    js = Template(MARKDOWN_JS).safe_substitute(raw_url=raw_url_js)
    return Template(_MARKDOWN_TEMPLATE).safe_substitute(
        css=MARKDOWN_CSS,
        js=js,
        filename=filename,
        raw_url=raw_url,
        parent_url=parent_url,
    )
