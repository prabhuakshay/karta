"""HTML page template for neev directory listings."""

PAGE_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en" class="antialiased">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{dir_name} &mdash; neev</title>
  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/_neev/static/neev.css">
  <script defer src="/_neev/static/alpine.min.js"></script>
</head>
<body class="bg-surface-0 text-ink-700 font-sans min-h-screen
  flex flex-col">

  <header class="bg-surface-1/80 backdrop-blur-lg border-b
    border-surface-3 sticky top-0 z-10">
    <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8
      h-14 flex items-center justify-between">
      <div class="flex items-center gap-3 min-w-0">
        <a href="/" class="flex items-center gap-2 shrink-0
          group" title="neev root">
          <div class="w-7 h-7 rounded-lg bg-gradient-to-br
            from-sage-400 to-sage-600 flex items-center
            justify-center shadow-card
            group-hover:shadow-card-md transition-shadow
            duration-200">
            <span class="text-white font-bold
              text-xs leading-none">N</span>
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
        {logout_html}
      </div>
    </div>
  </header>

  <main class="max-w-5xl mx-auto w-full px-4 sm:px-6
    lg:px-8 py-5 flex-1"
    :class="selectMode && selected.length > 0 ? 'pb-20' : ''"
    x-data="{{
      filter: '',
      downloadMode: localStorage.getItem('neev-download-mode') === 'true',
      selectMode: false,
      selected: [],
      toggleItem(name) {{
        const idx = this.selected.indexOf(name);
        if (idx === -1) this.selected.push(name);
        else this.selected.splice(idx, 1);
      }},
      isSelected(name) {{ return this.selected.indexOf(name) !== -1; }}
    }}"
    x-effect="
      localStorage.setItem('neev-download-mode', downloadMode);
      $el.querySelectorAll('.file-link').forEach(a => {{
        const base = a.getAttribute('data-href');
        if (!base) return;
        const preview = a.getAttribute('data-preview-href');
        a.href = downloadMode ? base + '?download' : (preview || base);
      }});
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

    {banner_html}

    <div class="flex items-center justify-between gap-3
      mb-4">
      <div class="relative">
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
            bg-surface-1 border border-surface-4
            rounded-md text-sm text-ink-700
            placeholder:text-ink-300
            hover:border-ink-300
            focus:border-sage-400 focus:bg-surface-1
            focus:ring-2 focus:ring-sage-50
            transition-colors duration-150">
      </div>
      <div class="flex items-center gap-2">
        <button @click="downloadMode = !downloadMode"
          class="inline-flex items-center gap-2
            px-3.5 py-2 bg-surface-1 text-ink-700 text-sm
            font-semibold rounded-lg border border-surface-3
            hover:bg-surface-2 active:bg-surface-3
            transition-colors duration-150 whitespace-nowrap"
          :title="downloadMode
            ? 'Switch to preview mode'
            : 'Switch to download mode'">
          <template x-if="!downloadMode">
            <svg class="w-4 h-4" fill="none"
              stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round"
                stroke-linejoin="round" stroke-width="2"
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
              <path stroke-linecap="round"
                stroke-linejoin="round" stroke-width="2"
                d="M2.458 12C3.732 7.943 7.523 5 12 5
                  c4.478 0 8.268 2.943 9.542 7
                  -1.274 4.057-5.064 7-9.542 7
                  -4.477 0-8.268-2.943-9.542-7z"/>
            </svg>
          </template>
          <template x-if="downloadMode">
            <svg class="w-4 h-4" fill="none"
              stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round"
                stroke-linejoin="round" stroke-width="2"
                d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4
                  M7 10l5 5 5-5 M12 15V3"/>
            </svg>
          </template>
          <span x-text="downloadMode
            ? 'Download' : 'Preview'"
            class="hidden sm:inline"></span>
        </button>
        {zip_html}
      </div>
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

    {select_bar_html}
  </main>

  <footer class="max-w-5xl mx-auto w-full px-4 sm:px-6
    lg:px-8 py-4">
    <p class="text-xs text-ink-300 text-center
      tracking-wide">
      served by
      <a href="https://github.com/prabhuakshay/neev"
        class="font-medium text-ink-400 hover:text-ink-500
        underline decoration-ink-200 hover:decoration-ink-400
        transition-colors" target="_blank"
        rel="noopener noreferrer">neev</a>
    </p>
  </footer>

  <script>
  function copyLink(ev, href) {{
    const btn = ev.currentTarget;
    const url = location.origin + href;
    function onCopied() {{
      const copyIcon = btn.querySelector('.icon-copy');
      const checkIcon = btn.querySelector('.icon-check');
      if (copyIcon) copyIcon.style.display = 'none';
      if (checkIcon) checkIcon.style.display = '';
      btn.classList.add('text-sage-500');
      btn.style.opacity = '1';
      setTimeout(() => {{
        if (copyIcon) copyIcon.style.display = '';
        if (checkIcon) checkIcon.style.display = 'none';
        btn.classList.remove('text-sage-500');
        btn.style.opacity = '';
      }}, 1500);
    }}
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      navigator.clipboard.writeText(url).then(onCopied);
    }} else {{
      const ta = document.createElement('textarea');
      ta.value = url;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      onCopied();
    }}
  }}
  function submitZip(action, items) {{
    const f = document.createElement('form');
    f.method = 'POST';
    f.action = action;
    items.forEach(function(n) {{
      const i = document.createElement('input');
      i.type = 'hidden';
      i.name = 'items';
      i.value = n;
      f.appendChild(i);
    }});
    document.body.appendChild(f);
    f.submit();
  }}
  </script>
</body>
</html>"""
