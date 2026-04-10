"""SVG icon definitions for file-type-aware directory listings.

Uses Lucide icon paths (24x24 viewBox, stroke-based) for clean,
professional file-type icons. Each extension maps to a distinct
icon shape and Lumina color.
"""

from pathlib import PurePosixPath


# -- Lucide SVG paths (24x24 viewBox) ----------------------------------------

_FOLDER = (
    '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 '
    "1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 "
    '0 0 0 2 2Z"/>'
)

_FILE = (
    '<path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 '
    "1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 "
    '2z"/><path d="M14 2v5a1 1 0 0 0 1 1h5"/>'
)

_FILE_CODE = (
    '<path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 '
    "1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 "
    '2z"/><path d="M14 2v5a1 1 0 0 0 1 1h5"/>'
    '<path d="M10 12.5 8 15l2 2.5"/><path d="m14 12.5 2 2.5-2 2.5"/>'
)

_FILE_TEXT = (
    '<path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 '
    "1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 "
    '2z"/><path d="M14 2v5a1 1 0 0 0 1 1h5"/>'
    '<path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>'
)

_IMAGE = (
    '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/>'
    '<circle cx="9" cy="9" r="2"/>'
    '<path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>'
)

_PACKAGE = (
    '<path d="M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 '
    "0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 "
    '0 0 0 1 1.73z"/><path d="M12 22V12"/>'
    '<polyline points="3.29 7 12 12 20.71 7"/>'
    '<path d="m7.5 4.27 9 5.15"/>'
)

_TERMINAL = '<path d="M12 19h8"/><path d="m4 17 6-6-6-6"/>'

_SETTINGS = (
    '<path d="M9.671 4.136a2.34 2.34 0 0 1 4.659 0 2.34 2.34 0 0 '
    "0 3.319 1.915 2.34 2.34 0 0 1 2.33 4.033 2.34 2.34 0 0 0 0 "
    "3.831 2.34 2.34 0 0 1-2.33 4.033 2.34 2.34 0 0 0-3.319 "
    "1.915 2.34 2.34 0 0 1-4.659 0 2.34 2.34 0 0 0-3.32-1.915 "
    "2.34 2.34 0 0 1-2.33-4.033 2.34 2.34 0 0 0 0-3.831A2.34 "
    '2.34 0 0 1 6.35 6.051a2.34 2.34 0 0 0 3.319-1.915"/>'
    '<circle cx="12" cy="12" r="3"/>'
)

_DATABASE = (
    '<ellipse cx="12" cy="5" rx="9" ry="3"/>'
    '<path d="M3 5V19A9 3 0 0 0 21 19V5"/>'
    '<path d="M3 12A9 3 0 0 0 21 12"/>'
)

_FILM = (
    '<rect width="18" height="18" x="3" y="3" rx="2"/>'
    '<path d="M7 3v18"/><path d="M3 7.5h4"/><path d="M3 12h18"/>'
    '<path d="M3 16.5h4"/><path d="M17 3v18"/>'
    '<path d="M17 7.5h4"/><path d="M17 16.5h4"/>'
)

_MUSIC = '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>'

_TYPE = '<path d="M12 4v16"/><path d="M4 7V5a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v2"/><path d="M9 20h6"/>'

_CODE_XML = '<path d="m18 16 4-4-4-4"/><path d="m6 8-4 4 4 4"/><path d="m14.5 4-5 16"/>'

_BRACES = (
    '<path d="M8 3H7a2 2 0 0 0-2 2v5a2 2 0 0 1-2 2 2 2 0 0 1 2 '
    '2v5c0 1.1.9 2 2 2h1"/>'
    '<path d="M16 21h1a2 2 0 0 0 2-2v-5c0-1.1.9-2 2-2a2 2 0 0 '
    '1-2-2V5a2 2 0 0 0-2-2h-1"/>'
)

_PAINTBRUSH = (
    '<path d="m14.622 17.897-10.68-2.913"/>'
    '<path d="M18.376 2.622a1 1 0 1 1 3.002 3.002L17.36 9.643a.5'
    ".5 0 0 0 0 .707l.944.944a2.41 2.41 0 0 1 0 3.408l-.944.944"
    "a.5.5 0 0 1-.707 0L8.354 7.348a.5.5 0 0 1 0-.707l.944-.944"
    'a2.41 2.41 0 0 1 3.408 0l.944.944a.5.5 0 0 0 .707 0z"/>'
    '<path d="M9 8c-1.804 2.71-3.97 3.46-6.583 3.948a.507.507 0 '
    "0 0-.302.819l7.32 8.883a1 1 0 0 0 1.185.204C12.735 20.405 "
    '16 16.792 16 15"/>'
)


# -- Extension lookup table ---------------------------------------------------

_IconSpec = tuple[str, str]
_DEFAULT: _IconSpec = (_FILE, "text-ink-300")

_EXT_MAP: dict[str, _IconSpec] = {}


def _register(exts: set[str], icon: str, color: str) -> None:
    """Register a set of extensions to an icon+color pair."""
    for ext in exts:
        _EXT_MAP[ext] = (icon, color)


_register({".py", ".pyw", ".pyx", ".pyi"}, _FILE_CODE, "text-sage-400")
_register({".js", ".ts", ".mjs", ".cjs"}, _BRACES, "text-amber-500")
_register(
    {".html", ".htm", ".xml", ".vue", ".svelte", ".jsx", ".tsx"},
    _CODE_XML,
    "text-ruby-500",
)
_register({".css", ".scss", ".sass", ".less"}, _PAINTBRUSH, "text-cyan-500")
_register(
    {".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd"},
    _TERMINAL,
    "text-sage-400",
)
_register(
    {
        ".toml",
        ".yaml",
        ".yml",
        ".json",
        ".ini",
        ".cfg",
        ".conf",
        ".env",
        ".lock",
        ".editorconfig",
    },
    _SETTINGS,
    "text-amber-500",
)
_register(
    {".md", ".txt", ".rst", ".pdf", ".doc", ".docx", ".csv", ".rtf"},
    _FILE_TEXT,
    "text-cyan-500",
)
_register(
    {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".bmp", ".tiff"},
    _IMAGE,
    "text-ruby-500",
)
_register(
    {".mp4", ".avi", ".mkv", ".mov", ".webm", ".flv"},
    _FILM,
    "text-ruby-500",
)
_register(
    {".mp3", ".wav", ".flac", ".ogg", ".aac", ".m4a", ".wma"},
    _MUSIC,
    "text-ruby-500",
)
_register(
    {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".tgz"},
    _PACKAGE,
    "text-ink-500",
)
_register({".sql", ".db", ".sqlite", ".sqlite3"}, _DATABASE, "text-cyan-500")
_register({".ttf", ".otf", ".woff", ".woff2", ".eot"}, _TYPE, "text-ink-500")
_register(
    {
        ".go",
        ".rs",
        ".rb",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".swift",
        ".kt",
        ".scala",
        ".r",
        ".lua",
        ".perl",
        ".pl",
        ".php",
        ".dart",
        ".zig",
        ".nim",
        ".ex",
        ".exs",
        ".hs",
        ".ml",
        ".clj",
    },
    _FILE_CODE,
    "text-sage-400",
)


# -- Public API ---------------------------------------------------------------


def icon_for_entry(name: str, is_dir: bool) -> str:
    """Return a complete SVG element for a file or directory.

    Args:
        name: The filename.
        is_dir: Whether the entry is a directory.

    Returns:
        HTML SVG element string with appropriate icon and color.
    """
    if is_dir:
        return _svg(_FOLDER, "text-sage-400", fill=True)

    ext = PurePosixPath(name).suffix.lower()
    svg_path, color = _EXT_MAP.get(ext, _DEFAULT)
    return _svg(svg_path, color)


def _svg(inner: str, color: str, *, fill: bool = False) -> str:
    """Wrap SVG path content in a complete SVG element."""
    if fill:
        return (
            f'<svg class="w-5 h-5 {color} shrink-0" '
            f'fill="currentColor" viewBox="0 0 24 24">{inner}</svg>'
        )
    return (
        f'<svg class="w-5 h-5 {color} shrink-0" fill="none" '
        f'stroke="currentColor" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round" '
        f'viewBox="0 0 24 24">{inner}</svg>'
    )
