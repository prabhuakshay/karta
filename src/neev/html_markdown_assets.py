"""Inline CSS and JavaScript for the markdown preview page.

Extracted from ``html_markdown.py`` to keep both files under the line limit.
These strings are interpolated into the markdown preview HTML template.
"""

MARKDOWN_CSS = """\
    .md-body { line-height: 1.7; color: #332F2A; }
    .md-body h1 { font-size: 1.75rem; font-weight: 800; color: #211E1A;
      margin: 2rem 0 1rem; padding-bottom: 0.5rem;
      border-bottom: 1px solid #E5E1DA; }
    .md-body h2 { font-size: 1.35rem; font-weight: 700; color: #211E1A;
      margin: 1.75rem 0 0.75rem; padding-bottom: 0.375rem;
      border-bottom: 1px solid #E5E1DA; }
    .md-body h3 { font-size: 1.125rem; font-weight: 700; color: #211E1A;
      margin: 1.5rem 0 0.5rem; }
    .md-body h4 { font-size: 1rem; font-weight: 700; color: #4A463F;
      margin: 1.25rem 0 0.5rem; }
    .md-body h5, .md-body h6 { font-size: 0.875rem; font-weight: 700;
      color: #4A463F; margin: 1rem 0 0.5rem; }
    .md-body p { margin: 0.75rem 0; }
    .md-body a { color: #47806D; text-decoration: none; }
    .md-body a:hover { text-decoration: underline; }
    .md-body pre { background: #F2EFEA; border-radius: 10px;
      padding: 1rem 1.25rem; overflow-x: auto; margin: 1rem 0;
      font-family: "JetBrains Mono", monospace; font-size: 0.8125rem;
      line-height: 1.6; position: relative; }
    .md-body code { font-family: "JetBrains Mono", monospace;
      font-size: 0.85em; }
    .md-body :not(pre) > code { background: #F2EFEA;
      border-radius: 4px; padding: 0.15em 0.4em; }
    .md-body ul, .md-body ol { padding-left: 1.75rem; margin: 0.75rem 0; }
    .md-body li { margin: 0.25rem 0; }
    .md-body li > ul, .md-body li > ol { margin: 0.25rem 0; }
    .md-body blockquote { border-left: 3px solid #5A9A84;
      background: #FFFFFF; padding: 0.75rem 1rem;
      margin: 1rem 0; color: #635E55; border-radius: 0 8px 8px 0; }
    .md-body blockquote p { margin: 0.25rem 0; }
    .md-body table { width: 100%; border-collapse: collapse;
      margin: 1rem 0; font-size: 0.875rem; }
    .md-body th { background: #F2EFEA; font-weight: 600;
      text-align: left; padding: 0.5rem 0.75rem;
      border: 1px solid #E5E1DA; }
    .md-body td { padding: 0.5rem 0.75rem;
      border: 1px solid #E5E1DA; }
    .md-body img { max-width: 100%; border-radius: 8px;
      margin: 1rem 0; }
    .md-body hr { border: none; border-top: 1px solid #E5E1DA;
      margin: 2rem 0; }
    .md-body input[type="checkbox"] { margin-right: 0.5rem; }
    .md-body li:has(> input[type="checkbox"]) {
      list-style: none; margin-left: -1.25rem; }
    .md-body del { color: #8C8780; text-decoration: line-through; }
    .md-body .mermaid { background: #FFFFFF; border-radius: 10px;
      padding: 1.5rem; margin: 1rem 0; text-align: center; }
    .md-body pre code.hljs { background: transparent;
      padding: 0; font-size: inherit; }
    .md-body .code-copy {
      position: absolute; top: 0.5rem; right: 0.5rem;
      background: #E5E1DA; border: none; border-radius: 6px;
      padding: 0.35rem 0.5rem; cursor: pointer; opacity: 0;
      transition: opacity 150ms; color: #635E55;
      font-size: 0.75rem; font-family: inherit; }
    .md-body pre:hover .code-copy { opacity: 1; }
    .md-body .code-copy:active { background: #D5D1CA; }
    .md-body h1 .heading-anchor, .md-body h2 .heading-anchor,
    .md-body h3 .heading-anchor, .md-body h4 .heading-anchor,
    .md-body h5 .heading-anchor, .md-body h6 .heading-anchor {
      opacity: 0; margin-left: 0.35rem; color: #5A9A84;
      text-decoration: none; font-weight: 400;
      transition: opacity 150ms; }
    .md-body h1:hover .heading-anchor, .md-body h2:hover .heading-anchor,
    .md-body h3:hover .heading-anchor, .md-body h4:hover .heading-anchor,
    .md-body h5:hover .heading-anchor, .md-body h6:hover .heading-anchor {
      opacity: 1; }"""

MARKDOWN_JS = """\
    (function() {
      var rawUrl = $raw_url;
      var mdEl = document.getElementById("md-content");
      var rawEl = document.getElementById("raw-content");
      var renderedEl = document.getElementById("rendered");
      var rawViewEl = document.getElementById("raw-view");
      var toggleBtn = document.getElementById("raw-toggle");
      var showRaw = false;
      var rawText = "";

      function sanitize(html) {
        if (typeof DOMPurify !== "undefined") {
          return DOMPurify.sanitize(html, {
            ADD_TAGS: ["pre"],
            ADD_ATTR: ["class", "id"]
          });
        }
        return html;
      }

      toggleBtn.addEventListener("click", function() {
        showRaw = !showRaw;
        renderedEl.classList.toggle("hidden", showRaw);
        rawViewEl.classList.toggle("hidden", !showRaw);
        toggleBtn.querySelector("span").textContent =
          showRaw ? "Rendered" : "Raw";
      });

      fetch(rawUrl).then(function(r) {
        if (!r.ok) throw new Error(r.status);
        return r.text();
      }).then(function(text) {
        rawText = text;
        rawEl.textContent = text;
        renderMarkdown(text);
      }).catch(function() {
        mdEl.textContent = "Failed to load file content.";
      });

      function renderMarkdown(text) {
        if (typeof marked === "undefined") {
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
        }

        var renderer = new marked.Renderer();
        renderer.code = function(obj) {
          if (obj.lang === "mermaid") {
            return '<pre class="mermaid">' +
              escapeHtml(obj.text) + "</pre>";
          }
          var langClass = obj.lang
            ? ' class="language-' + escapeHtml(obj.lang) + '"'
            : "";
          return '<pre><code' + langClass + '>' +
            escapeHtml(obj.text) + "</code></pre>";
        };
        renderer.heading = function(obj) {
          var slug = obj.text.toLowerCase()
            .replace(/<[^>]+>/g, "")
            .replace(/[^\\w\\s-]/g, "")
            .replace(/\\s+/g, "-");
          return "<h" + obj.depth + ' id="' + slug + '">' +
            obj.text +
            '<a class="heading-anchor" href="#' + slug +
            '" aria-label="Link to this section">#</a>' +
            "</h" + obj.depth + ">";
        };

        marked.setOptions({
          renderer: renderer, breaks: false, gfm: true
        });
        var parsed = marked.parse(text);
        mdEl.textContent = "";
        mdEl.insertAdjacentHTML("afterbegin", sanitize(parsed));
        highlightCode();
        addCopyButtons();
        initMermaid();
      }

      function initMermaid() {
        if (typeof mermaid === "undefined") return;
        mermaid.initialize({
          startOnLoad: false,
          theme: "neutral",
          fontFamily: "Plus Jakarta Sans, system-ui, sans-serif"
        });
        mermaid.run({ querySelector: ".mermaid" });
      }

      function highlightCode() {
        if (typeof hljs === "undefined") return;
        mdEl.querySelectorAll("pre code[class*='language-']")
          .forEach(function(block) {
            hljs.highlightElement(block);
          });
      }

      function addCopyButtons() {
        mdEl.querySelectorAll("pre:not(.mermaid)").forEach(
          function(pre) {
            var btn = document.createElement("button");
            btn.className = "code-copy";
            btn.textContent = "Copy";
            btn.addEventListener("click", function() {
              var code = pre.querySelector("code");
              var text = code ? code.textContent : pre.textContent;
              navigator.clipboard.writeText(text).then(function() {
                btn.textContent = "Copied!";
                setTimeout(function() {
                  btn.textContent = "Copy";
                }, 1500);
              });
            });
            pre.appendChild(btn);
          });
      }

      function escapeHtml(s) {
        var d = document.createElement("div");
        d.appendChild(document.createTextNode(s));
        return d.innerHTML;
      }

      /* Re-render once all resources settle: either apply CDN
         libs that arrived late, or show the offline fallback */
      window.addEventListener("load", function() {
        if (rawText) renderMarkdown(rawText);
      });

      /* Safety-net: if the spinner is still showing after 5s
         (e.g. CDN scripts blocking window.load), force the
         offline fallback so the page never hangs indefinitely */
      setTimeout(function() {
        if (rawText && mdEl.querySelector(".animate-spin")) {
          renderMarkdown(rawText);
        }
      }, 5000);
    })();"""
