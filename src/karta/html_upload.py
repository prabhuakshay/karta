"""HTML rendering for upload and create-folder forms.

Builds form HTML injected into the directory listing page when
``enable_upload`` is True. Matches Lumina theme styling.
"""

import html


# -- SVG icons ----------------------------------------------------------------

_UPLOAD_ICON = (
    '<svg class="w-4 h-4" fill="none" stroke="currentColor" '
    'viewBox="0 0 24 24"><path stroke-linecap="round" '
    'stroke-linejoin="round" stroke-width="2" '
    'd="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4m14-7l-5-5-5 5'
    'm5-5v12"/></svg>'
)

_FOLDER_PLUS_ICON = (
    '<svg class="w-4 h-4" fill="none" stroke="currentColor" '
    'viewBox="0 0 24 24"><path stroke-linecap="round" '
    'stroke-linejoin="round" stroke-width="2" '
    'd="M9 13h6m-3-3v6m-9 1V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8'
    'a2 2 0 01-2 2H5a2 2 0 01-2-2z"/></svg>'
)


# -- Reusable class strings ---------------------------------------------------

_INPUT_CLS = (
    "w-full px-3.5 py-2.5 bg-surface-2 border border-surface-3 "
    "rounded-md text-sm text-ink-700 placeholder:text-ink-300 "
    "hover:border-surface-4 focus:border-sage-400 focus:bg-surface-1 "
    "focus:ring-2 focus:ring-sage-50 transition-colors duration-150"
)

_BTN_PRIMARY = (
    "inline-flex items-center gap-2 px-5 py-2 bg-sage-400 "
    "text-white text-sm font-semibold rounded-lg hover:bg-sage-500 "
    "active:bg-sage-600 transition-colors duration-150"
)

_BTN_SECONDARY = (
    "inline-flex items-center gap-2 px-5 py-2 bg-surface-1 "
    "text-ink-700 text-sm font-semibold rounded-lg border "
    "border-surface-3 hover:bg-surface-2 active:bg-surface-3 "
    "transition-colors duration-150"
)


# -- Public API ---------------------------------------------------------------


def render_upload_section(request_path: str) -> str:
    """Render the upload and create-folder forms section.

    Args:
        request_path: The current request URL path (form action target).

    Returns:
        HTML string with both forms in a card container.
    """
    action = html.escape(request_path)
    mkdir_action = html.escape(request_path.rstrip("/") + "/")

    return (
        f'<div class="mt-5" x-data="{{ mode: \'file\' }}">'
        f'<div class="bg-surface-1 shadow-card rounded-xl '
        f'overflow-hidden">'
        # Section header with tab toggle
        f'<div class="px-4 py-3 border-b border-surface-3 '
        f'flex items-center">'
        f'<div class="flex items-center gap-4">'
        f"{_tab_button('file', 'Upload', _UPLOAD_ICON)}"
        f"{_tab_button('folder', 'New folder', _FOLDER_PLUS_ICON)}"
        f"</div>"
        f"</div>"
        # Upload form panel
        f"<div x-show=\"mode === 'file'\" x-cloak>"
        f"{_render_file_upload_form(action)}"
        f"</div>"
        # Create folder panel
        f"<div x-show=\"mode === 'folder'\" x-cloak>"
        f"{_render_create_folder_form(mkdir_action)}"
        f"</div>"
        f"</div>"
        f"</div>"
    )


# -- Private helpers ----------------------------------------------------------


def _tab_button(mode: str, label: str, icon: str) -> str:
    """Render a tab toggle button for the upload section header.

    Args:
        mode: The Alpine ``mode`` value this tab activates.
        label: Button text label.
        icon: SVG icon HTML string.

    Returns:
        HTML button string.
    """
    return (
        f'<button type="button" '
        f"@click=\"mode = '{mode}'\" "
        f":class=\"mode === '{mode}' "
        f"? 'text-sage-500 font-semibold' "
        f": 'text-ink-400 hover:text-ink-700'\" "
        f'class="text-sm transition-colors duration-150 '
        f'flex items-center gap-1.5">'
        f"{icon} {label}</button>"
    )


def _render_file_upload_form(action: str) -> str:
    """Render the file/folder upload form.

    Args:
        action: HTML-escaped form action URL.

    Returns:
        HTML string for the upload form body.
    """
    file_input_cls = (
        "block w-full text-sm text-ink-500 "
        "file:mr-3 file:py-2 file:px-4 file:rounded-lg "
        "file:border-0 file:text-sm file:font-semibold "
        "file:bg-surface-2 file:text-ink-700 "
        "hover:file:bg-surface-3 file:cursor-pointer"
    )

    return (
        f'<form method="POST" action="{action}" '
        f'enctype="multipart/form-data" '
        f"x-data=\"{{ uploadType: 'files' }}\" "
        f'x-on:submit="prepareUpload($event)">'
        # Upload type toggle (files vs folder)
        f'<div class="px-4 pt-3 flex items-center gap-3">'
        f'<label class="flex items-center gap-2 text-xs '
        f'text-ink-500 cursor-pointer">'
        f'<input type="radio" name="uploadType" value="files" '
        f'x-model="uploadType" class="accent-sage-400"> Files</label>'
        f'<label class="flex items-center gap-2 text-xs '
        f'text-ink-500 cursor-pointer">'
        f'<input type="radio" name="uploadType" value="folder" '
        f'x-model="uploadType" class="accent-sage-400"> Folder</label>'
        f"</div>"
        # File input area
        f'<div class="px-4 pt-3 pb-4">'
        f"<div x-show=\"uploadType === 'files'\">"
        f'<input type="file" name="file" multiple '
        f'class="{file_input_cls}">'
        f"</div>"
        f"<div x-show=\"uploadType === 'folder'\" x-cloak>"
        f'<input type="file" name="file" multiple webkitdirectory '
        f'class="{file_input_cls}">'
        f"</div>"
        # Hidden container for relativePath values (populated by JS)
        f'<div id="relativePathFields"></div>'
        f'<div class="flex items-center justify-between mt-3">'
        f'<p class="text-xs text-ink-300">100 MB size limit</p>'
        f'<button type="submit" class="{_BTN_PRIMARY}">'
        f"{_UPLOAD_ICON} Upload</button>"
        f"</div>"
        f"</div>"
        f"</form>"
        f"{_FOLDER_UPLOAD_SCRIPT}"
    )


def _render_create_folder_form(action: str) -> str:
    """Render the create folder form.

    Args:
        action: HTML-escaped base action URL (mkdir param appended via JS).

    Returns:
        HTML string for the create folder form body.
    """
    return (
        f'<form method="POST" '
        f"x-data=\"{{ folderName: '' }}\" "
        f'x-on:submit.prevent="'
        f"if (folderName.trim()) {{ "
        f"$el.action = '{action}' + '?mkdir=' + "
        f"encodeURIComponent(folderName.trim()); "
        f"$el.submit(); "
        f'}} ">'
        f'<div class="px-4 pt-3 pb-4">'
        f'<div class="flex gap-3">'
        f'<input type="text" x-model="folderName" '
        f'placeholder="Folder name" '
        f'class="{_INPUT_CLS} flex-1" required>'
        f'<button type="submit" class="{_BTN_SECONDARY}">'
        f"{_FOLDER_PLUS_ICON} Create</button>"
        f"</div>"
        f"</div>"
        f"</form>"
    )


_FOLDER_UPLOAD_SCRIPT = """\
<script>
function prepareUpload(event) {
  var container = document.getElementById('relativePathFields');
  while (container.firstChild) {
    container.removeChild(container.firstChild);
  }
  var form = event.target;
  var fileInputs = form.querySelectorAll('input[type="file"]');
  for (var i = 0; i < fileInputs.length; i++) {
    var input = fileInputs[i];
    if (!input.offsetParent) continue;
    var files = input.files;
    for (var j = 0; j < files.length; j++) {
      var relPath = files[j].webkitRelativePath || '';
      if (relPath) {
        var hidden = document.createElement('input');
        hidden.type = 'hidden';
        hidden.name = 'relativePath';
        hidden.value = relPath;
        container.appendChild(hidden);
      }
    }
    break;
  }
}
</script>"""
