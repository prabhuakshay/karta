"""Shared HTTP helpers for neev server modules."""

from http.server import BaseHTTPRequestHandler


def send_error(handler: BaseHTTPRequestHandler, code: int, message: str | bytes) -> None:
    """Send a plain-text error response.

    Args:
        handler: The active request handler.
        code: HTTP status code.
        message: Error message body; ``str`` is UTF-8 encoded.
    """
    body = message.encode() if isinstance(message, str) else message
    handler.send_response(code)
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)
