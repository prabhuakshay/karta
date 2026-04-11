"""ANSI styling helpers for request logging."""

import sys
from typing import TextIO


def ansi_styled(text: str, code: str, *, stream: TextIO = sys.stderr) -> str:
    """Wrap text in ANSI escape codes if the stream is a terminal.

    Args:
        text: The string to style.
        code: ANSI SGR code (e.g. ``"1"`` for bold, ``"32"`` for green).
        stream: The output stream to check for TTY support.

    Returns:
        The styled string, or the original text if the stream is not a terminal.
    """
    if not stream.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def status_color(status: int) -> str:
    """Return an ANSI-colored status code string.

    Args:
        status: HTTP status code.

    Returns:
        Color-coded status string (green for 2xx, yellow for 3xx, red for 4xx+).
    """
    text = str(status)
    if 200 <= status < 300:
        return ansi_styled(text, "32")
    if 300 <= status < 400:
        return ansi_styled(text, "33")
    return ansi_styled(text, "31")
