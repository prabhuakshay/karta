"""ANSI styling helpers for request logging."""

import sys


def log_styled(text: str, code: str) -> str:
    """Wrap text in ANSI escape codes if stderr is a terminal.

    Args:
        text: The string to style.
        code: ANSI SGR code.

    Returns:
        The styled string, or the original text if stderr is not a terminal.
    """
    if not sys.stderr.isatty():
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
        return log_styled(text, "32")
    if 300 <= status < 400:
        return log_styled(text, "33")
    return log_styled(text, "31")
