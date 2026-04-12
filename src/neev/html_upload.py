"""HTML rendering for upload and create-folder forms.

Builds form HTML injected into the directory listing page when
``enable_upload`` is True. Matches Lumina theme styling.
"""

from neev.html_upload_js import get_upload_script
from neev.url_utils import encode_attr_url


# -- SVG icons ----------------------------------------------------------------

_UPLOAD_ICON_LG = (
    '<svg class="w-8 h-8" aria-hidden="true" fill="none" stroke="currentColor" '
    'stroke-width="1.5" viewBox="0 0 24 24">'
    '<path stroke-linecap="round" stroke-linejoin="round" '
    'd="M12 16V4m0 0l-4 4m4-4l4 4"/>'
    '<path stroke-linecap="round" stroke-linejoin="round" '
    'd="M20 16v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2"/></svg>'
)

_FOLDER_PLUS_ICON = (
    '<svg class="w-4 h-4" aria-hidden="true" fill="none" stroke="currentColor" '
    'viewBox="0 0 24 24"><path stroke-linecap="round" '
    'stroke-linejoin="round" stroke-width="2" '
    'd="M9 13h6m-3-3v6m-9 1V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8'
    'a2 2 0 01-2 2H5a2 2 0 01-2-2z"/></svg>'
)

_X_ICON = (
    '<svg class="w-3.5 h-3.5" aria-hidden="true" fill="none" stroke="currentColor" '
    'viewBox="0 0 24 24"><path stroke-linecap="round" '
    'stroke-linejoin="round" stroke-width="2" '
    'd="M6 18L18 6M6 6l12 12"/></svg>'
)

_FILE_ICON = (
    '<svg class="w-4 h-4 text-ink-400 shrink-0" aria-hidden="true" fill="none" '
    'stroke="currentColor" viewBox="0 0 24 24">'
    '<path stroke-linecap="round" stroke-linejoin="round" '
    'stroke-width="2" d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 '
    '2h12a2 2 0 002-2V8z"/>'
    '<polyline stroke-linecap="round" stroke-linejoin="round" '
    'stroke-width="2" points="14 2 14 8 20 8"/></svg>'
)


# -- Reusable class strings ---------------------------------------------------

_BTN_PRIMARY = (
    "inline-flex items-center gap-2 px-5 py-2 bg-sage-400 "
    "text-white text-sm font-semibold rounded-lg hover:bg-sage-600 "
    "hover:shadow-md active:bg-sage-700 transition-all duration-150"
)

_INPUT_CLS = (
    "w-full px-3.5 py-2 bg-surface-1 border border-surface-4 "
    "rounded-lg text-sm text-ink-700 placeholder:text-ink-300 "
    "hover:border-ink-300 focus:border-sage-400 "
    "focus:ring-2 focus:ring-sage-50 transition-colors duration-150"
)

_SEG_BTN = (
    "px-3.5 py-1.5 text-xs font-semibold rounded-md transition-all duration-150 cursor-pointer"
)
_SEG_ON = "bg-white text-ink-700 shadow-sm"
_SEG_OFF = "text-ink-400 hover:text-ink-600"


# -- Public API ---------------------------------------------------------------


def render_upload_section(request_path: str) -> str:
    """Render the upload and create-folder forms section.

    Args:
        request_path: The current request URL path (form action target).

    Returns:
        HTML string — single card with drag-and-drop upload zone,
        file preview, and inline create-folder row.
    """
    action = encode_attr_url(request_path)
    mkdir_action = encode_attr_url(request_path.rstrip("/") + "/")

    return (
        # Single card wrapping everything
        f'<div class="mt-8 bg-surface-1 shadow-card rounded-xl '
        f'overflow-hidden" x-data="uploadZone" '
        f'@paste.window="handlePaste($event)">'
        f"{_render_upload_form(action)}"
        f"{_render_create_folder(mkdir_action)}"
        f"</div>"
        f"{get_upload_script()}"
    )


# -- Private helpers ----------------------------------------------------------


def _render_upload_form(action: str) -> str:
    """Render the upload form with drop zone and file preview.

    Args:
        action: The escaped URL the form POSTs to.

    Returns:
        HTML string — a ``<form>`` element containing the drop zone and
        file preview panel.
    """
    return (
        f'<form method="POST" action="{action}" '
        f'enctype="multipart/form-data" '
        f'x-ref="uploadForm" '
        f'x-on:submit="uploading = true">'
        f"{_drop_zone()}"
        f"{_file_preview()}"
        f"</form>"
    )


def _drop_zone() -> str:
    """Render the drag-and-drop target area.

    Returns:
        HTML string — a bordered dashed rectangle with upload icon, hint
        text, segmented Files/Folder toggle, and hidden file inputs.
    """
    return (
        f'<div class="p-5">'
        f"<div "
        f'@dragover.prevent="dragging = true" '
        f'@dragleave.prevent="dragging = false" '
        f'@drop.prevent="handleDrop($event)" '
        f"@click=\"mode === 'folder' "
        f"? $refs.folderInput.click() "
        f': $refs.fileInput.click()" '
        f':class="dragging '
        f"? 'border-sage-400 bg-sage-50/80 shadow-sm' "
        f": 'border-surface-4/80 hover:border-sage-300 "
        f"hover:bg-surface-0/30'\" "
        f'class="border-2 border-dashed rounded-xl py-10 px-6 '
        f'text-center cursor-pointer transition-all duration-200">'
        # Icon + text
        f'<div class="flex flex-col items-center gap-3">'
        f'<div class="w-14 h-14 rounded-2xl bg-sage-50 '
        f"flex items-center justify-center "
        f'text-sage-400">{_UPLOAD_ICON_LG}</div>'
        f"<div>"
        f'<p class="text-sm font-medium text-ink-600">'
        f"Drop files here or "
        f'<span class="text-sage-500 font-semibold">browse</span></p>'
        f'<p class="text-xs text-ink-300 mt-1">100 MB limit'
        f" &middot; or paste from clipboard</p>"
        f"</div>"
        # Segmented control inside the drop zone
        f"{_segmented_control()}"
        f"</div>"
        # Hidden inputs
        f'<input x-ref="fileInput" type="file" name="file" '
        f'multiple @change="handleFiles($event)" class="hidden">'
        f'<input x-ref="folderInput" type="file" name="file" '
        f"multiple webkitdirectory "
        f'@change="handleFiles($event)" class="hidden">'
        f'<div id="relativePathFields"></div>'
        f"</div>"
        f"</div>"
    )


def _segmented_control() -> str:
    """Render the Files/Folder segmented toggle.

    Returns:
        HTML string — two-button pill toggle that switches between
        individual-file and whole-folder upload mode.
    """
    return (
        f'<div class="inline-flex items-center bg-surface-2 '
        f'p-1 rounded-lg mt-3">'
        f'<button type="button" @click.stop="switchMode(\'files\')" '
        f":class=\"mode === 'files' "
        f"? '{_SEG_ON}' : '{_SEG_OFF}'\" "
        f'class="{_SEG_BTN}">Files</button>'
        f'<button type="button" @click.stop="switchMode(\'folder\')" '
        f":class=\"mode === 'folder' "
        f"? '{_SEG_ON}' : '{_SEG_OFF}'\" "
        f'class="{_SEG_BTN}">Folder</button>'
        f"</div>"
    )


def _file_preview() -> str:
    """Render the file list and submit bar (shown after selection).

    Returns:
        HTML string — a scrollable list of selected files with per-file
        remove buttons, followed by the submit bar.  Hidden until at
        least one file is queued (Alpine ``x-show``).
    """
    return (
        f'<div x-show="files.length > 0" x-cloak '
        f'class="border-t border-surface-3">'
        f'<div class="px-5 py-3 max-h-48 overflow-y-auto space-y-0.5">'
        f'<template x-for="(f, i) in files" :key="i">'
        f'<div class="flex items-center gap-2.5 py-1.5 px-2.5 '
        f"rounded-lg hover:bg-surface-2 group "
        f'transition-colors duration-100">'
        f"{_FILE_ICON}"
        f'<span x-text="f.name" class="text-sm text-ink-600 '
        f'truncate min-w-0 flex-1"></span>'
        f'<span x-text="formatSize(f.size)" '
        f'class="text-xs text-ink-300 tabular shrink-0"></span>'
        f'<button type="button" @click="removeFile(i)" '
        f'class="shrink-0 w-6 h-6 flex items-center '
        f"justify-center rounded text-ink-300 "
        f"hover:text-ruby-500 hover:bg-ruby-50 "
        f"opacity-0 group-hover:opacity-100 "
        f'transition-all duration-150" '
        f'aria-label="Remove file">{_X_ICON}</button>'
        f"</div>"
        f"</template>"
        f"</div>"
        f"{_submit_bar()}"
        f"</div>"
    )


def _submit_bar() -> str:
    """Render the file count and upload/clear buttons.

    Returns:
        HTML string — a footer row showing the selected-file count plus
        Clear and Upload action buttons.
    """
    return (
        f'<div class="px-5 py-3 border-t border-surface-3 '
        f'flex items-center justify-between bg-surface-2/40">'
        f'<p class="text-xs text-ink-400">'
        f'<span x-text="files.length" class="tabular-nums"></span>'
        f' file<span x-show="files.length !== 1">s</span> selected</p>'
        f'<div class="flex items-center gap-2">'
        f'<button type="button" @click="clearFiles()" '
        f'class="text-xs text-ink-400 hover:text-ink-600 '
        f'transition-colors duration-150">Clear</button>'
        f'<button type="submit" :disabled="uploading" '
        f":class=\"uploading && 'opacity-50 cursor-not-allowed'\" "
        f'class="{_BTN_PRIMARY}">'
        f'<span x-show="!uploading">Upload</span>'
        f'<span x-show="uploading" x-cloak>Uploading…</span>'
        f"</button>"
        f"</div>"
        f"</div>"
    )


def _render_create_folder(action: str) -> str:
    """Render the create-folder row at the bottom of the card.

    Args:
        action: The escaped base URL; ``?mkdir=<name>`` is appended
            client-side before submission.

    Returns:
        HTML string — a bordered footer row with a text input and
        Create button for making a new subdirectory.
    """
    return (
        f'<div class="border-t border-surface-3 bg-surface-2/30">'
        f'<form method="POST" '
        f"x-data=\"{{ folderName: '' }}\" "
        f'x-on:submit.prevent="'
        f"if (folderName.trim()) {{ "
        f"$el.action = '{action}' + '?mkdir=' + "
        f"encodeURIComponent(folderName.trim()); "
        f"$el.submit(); "
        f'}} ">'
        f'<div class="px-5 py-3 flex items-center gap-3">'
        f'<div class="text-ink-300 shrink-0">{_FOLDER_PLUS_ICON}</div>'
        f'<input type="text" x-model="folderName" '
        f'placeholder="New folder name" '
        f'class="{_INPUT_CLS} flex-1" required>'
        f'<button type="submit" '
        f'class="inline-flex items-center gap-1.5 px-4 py-2 '
        f"text-ink-500 text-sm font-semibold rounded-lg "
        f"hover:bg-surface-2 hover:text-ink-700 "
        f'transition-colors duration-150">'
        f"{_FOLDER_PLUS_ICON} Create</button>"
        f"</div>"
        f"</form>"
        f"</div>"
    )
