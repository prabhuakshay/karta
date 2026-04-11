"""HTML template for markdown file preview with Mermaid diagram support."""

_MARKDOWN_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en" class="antialiased">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{filename} &mdash; neev</title>
  <link rel="icon" href="/favicon.ico" type="image/svg+xml">
  <link rel="stylesheet" href="/_neev/static/neev.css">
  <script defer src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/dompurify/dist/purify.min.js"></script>
  <style>
    .md-body {{ line-height: 1.7; color: #332F2A; }}
    .md-body h1 {{ font-size: 1.75rem; font-weight: 800; color: #211E1A;
      margin: 2rem 0 1rem; padding-bottom: 0.5rem;
      border-bottom: 1px solid #E5E1DA; }}
    .md-body h2 {{ font-size: 1.35rem; font-weight: 700; color: #211E1A;
      margin: 1.75rem 0 0.75rem; padding-bottom: 0.375rem;
      border-bottom: 1px solid #E5E1DA; }}
    .md-body h3 {{ font-size: 1.125rem; font-weight: 700; color: #211E1A;
      margin: 1.5rem 0 0.5rem; }}
    .md-body h4 {{ font-size: 1rem; font-weight: 700; color: #4A463F;
      margin: 1.25rem 0 0.5rem; }}
    .md-body h5, .md-body h6 {{ font-size: 0.875rem; font-weight: 700;
      color: #4A463F; margin: 1rem 0 0.5rem; }}
    .md-body p {{ margin: 0.75rem 0; }}
    .md-body a {{ color: #47806D; text-decoration: none; }}
    .md-body a:hover {{ text-decoration: underline; }}
    .md-body pre {{ background: #F2EFEA; border-radius: 10px;
      padding: 1rem 1.25rem; overflow-x: auto; margin: 1rem 0;
      font-family: "JetBrains Mono", monospace; font-size: 0.8125rem;
      line-height: 1.6; }}
    .md-body code {{ font-family: "JetBrains Mono", monospace;
      font-size: 0.85em; }}
    .md-body :not(pre) > code {{ background: #F2EFEA;
      border-radius: 4px; padding: 0.15em 0.4em; }}
    .md-body ul, .md-body ol {{ padding-left: 1.75rem; margin: 0.75rem 0; }}
    .md-body li {{ margin: 0.25rem 0; }}
    .md-body li > ul, .md-body li > ol {{ margin: 0.25rem 0; }}
    .md-body blockquote {{ border-left: 3px solid #5A9A84;
      background: #FFFFFF; padding: 0.75rem 1rem;
      margin: 1rem 0; color: #635E55; border-radius: 0 8px 8px 0; }}
    .md-body blockquote p {{ margin: 0.25rem 0; }}
    .md-body table {{ width: 100%; border-collapse: collapse;
      margin: 1rem 0; font-size: 0.875rem; }}
    .md-body th {{ background: #F2EFEA; font-weight: 600;
      text-align: left; padding: 0.5rem 0.75rem;
      border: 1px solid #E5E1DA; }}
    .md-body td {{ padding: 0.5rem 0.75rem;
      border: 1px solid #E5E1DA; }}
    .md-body img {{ max-width: 100%; border-radius: 8px;
      margin: 1rem 0; }}
    .md-body hr {{ border: none; border-top: 1px solid #E5E1DA;
      margin: 2rem 0; }}
    .md-body input[type="checkbox"] {{ margin-right: 0.5rem; }}
    .md-body .mermaid {{ background: #FFFFFF; border-radius: 10px;
      padding: 1.5rem; margin: 1rem 0; text-align: center; }}
  </style>
</head>
<body class="bg-surface-0 text-ink-700 font-sans min-h-screen
  flex flex-col">

  <header class="bg-surface-1/80 backdrop-blur-lg border-b
    border-surface-3 sticky top-0 z-10">
    <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8
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
      <div class="flex items-center gap-2">
        <button id="raw-toggle"
          class="inline-flex items-center gap-2
            px-3.5 py-2 bg-surface-1 text-ink-700 text-sm
            font-semibold rounded-lg border border-surface-3
            hover:bg-surface-2 active:bg-surface-3
            transition-colors duration-150 whitespace-nowrap">
          <svg class="w-4 h-4" fill="none"
            stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round"
              stroke-width="2"
              d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/>
          </svg>
          <span class="hidden sm:inline">Raw</span>
        </button>
        <a href="{raw_url}"
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
    (function() {{
      var rawUrl = "{raw_url}";
      var mdEl = document.getElementById("md-content");
      var rawEl = document.getElementById("raw-content");
      var renderedEl = document.getElementById("rendered");
      var rawViewEl = document.getElementById("raw-view");
      var toggleBtn = document.getElementById("raw-toggle");
      var showRaw = false;
      var rawText = "";

      function sanitize(html) {{
        if (typeof DOMPurify !== "undefined") {{
          return DOMPurify.sanitize(html, {{
            ADD_TAGS: ["pre"],
            ADD_ATTR: ["class"]
          }});
        }}
        return html;
      }}

      toggleBtn.addEventListener("click", function() {{
        showRaw = !showRaw;
        renderedEl.classList.toggle("hidden", showRaw);
        rawViewEl.classList.toggle("hidden", !showRaw);
        toggleBtn.querySelector("span").textContent =
          showRaw ? "Rendered" : "Raw";
      }});

      fetch(rawUrl).then(function(r) {{
        if (!r.ok) throw new Error(r.status);
        return r.text();
      }}).then(function(text) {{
        rawText = text;
        rawEl.textContent = text;
        renderMarkdown(text);
      }}).catch(function() {{
        mdEl.textContent = "Failed to load file content.";
      }});

      function renderMarkdown(text) {{
        if (typeof marked === "undefined") {{
          var pre = document.createElement("pre");
          pre.style.whiteSpace = "pre-wrap";
          pre.style.wordBreak = "break-word";
          pre.textContent = text;
          var note = document.createElement("p");
          note.className = "text-xs text-ink-400 mt-4";
          note.textContent =
            "Markdown preview requires an internet connection.";
          mdEl.textContent = "";
          mdEl.appendChild(pre);
          mdEl.appendChild(note);
          return;
        }}

        var renderer = new marked.Renderer();
        renderer.code = function(obj) {{
          if (obj.lang === "mermaid") {{
            return '<pre class="mermaid">' +
              escapeHtml(obj.text) + "</pre>";
          }}
          return '<pre><code class="language-' +
            escapeHtml(obj.lang || "") + '">' +
            escapeHtml(obj.text) + "</code></pre>";
        }};

        marked.setOptions({{ renderer: renderer, breaks: false }});
        var parsed = marked.parse(text);
        mdEl.textContent = "";
        mdEl.insertAdjacentHTML("afterbegin", sanitize(parsed));
        initMermaid();
      }}

      function initMermaid() {{
        if (typeof mermaid === "undefined") return;
        mermaid.initialize({{
          startOnLoad: false,
          theme: "neutral",
          fontFamily: "Plus Jakarta Sans, system-ui, sans-serif"
        }});
        mermaid.run({{ querySelector: ".mermaid" }});
      }}

      function escapeHtml(s) {{
        var d = document.createElement("div");
        d.appendChild(document.createTextNode(s));
        return d.innerHTML;
      }}

      /* Retry rendering once CDN scripts finish loading */
      window.addEventListener("load", function() {{
        if (rawText && typeof marked !== "undefined"
            && mdEl.querySelector("pre:not(.mermaid)")) {{
          renderMarkdown(rawText);
        }}
      }});
    }})();
  </script>
</body>
</html>"""


def render_markdown_preview(filename: str, raw_url: str, parent_url: str) -> str:
    """Render an HTML page that previews a markdown file.

    Args:
        filename: Display name of the markdown file (pre-escaped).
        raw_url: URL to fetch the raw markdown content (pre-escaped).
        parent_url: URL of the parent directory (pre-escaped).

    Returns:
        Complete HTML page as a string.
    """
    return _MARKDOWN_TEMPLATE.format(
        filename=filename,
        raw_url=raw_url,
        parent_url=parent_url,
    )
