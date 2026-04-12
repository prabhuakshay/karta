"""Per-context encoding helpers for URLs, HTML attributes, JS, and headers.

Every rendering context (HTML attribute, URL path, JS-in-HTML, HTTP header)
needs its own escape. Centralizing them here keeps the rules consistent and
auditable — a security-sensitive concern we don't want duplicated.
"""

import html
import json
from urllib.parse import quote


def quote_path(path: str) -> str:
    """URL-encode a decoded URL path, preserving ``/`` separators.

    Args:
        path: The decoded URL path (e.g. ``/foo/bar baz/``).

    Returns:
        The path with each segment percent-encoded.
    """
    return quote(path, safe="/")


def encode_attr_url(path: str) -> str:
    """Encode a decoded URL path for safe use as an HTML attribute value.

    Applies URL-encoding first (so spaces, ``?``, ``#``, ``%`` are preserved
    as path literals), then HTML-escapes for attribute context.

    Args:
        path: The decoded URL path.

    Returns:
        A string safe to drop into an ``href`` or ``src`` attribute.
    """
    return html.escape(quote_path(path))


def js_string_escape(value: str) -> str:
    """Escape a string for safe use inside a JS single-quoted literal.

    Handles backslash, single-quote, and newline characters so the escaped
    form survives both HTML attribute decoding and JS parsing.

    Args:
        value: The raw string.

    Returns:
        The escaped string.
    """
    return value.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "\\r")


def script_safe_json(value: str) -> str:
    r"""JSON-encode a string for inclusion inside an inline ``<script>`` block.

    ``json.dumps`` alone does not escape ``<``, ``>``, or ``&``, so a value
    containing ``</script>`` would close the script tag. This variant escapes
    those characters using JSON ``\\uXXXX`` sequences.

    Args:
        value: The raw string.

    Returns:
        A JSON-encoded string literal (including quotes) safe for ``<script>``.
    """
    return json.dumps(value).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def is_valid_header_value(value: str) -> bool:
    """Check whether a string is safe to pass to ``send_header``.

    ``BaseHTTPRequestHandler.send_header`` does not validate CR/LF/NUL — a
    value containing those would enable response splitting. Callers should
    reject invalid values with a 400 before sending the header.

    Args:
        value: The candidate header value.

    Returns:
        ``True`` if the value contains no CR, LF, or NUL bytes.
    """
    return "\r" not in value and "\n" not in value and "\0" not in value
