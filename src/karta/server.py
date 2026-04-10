"""HTTP server and request handler for karta."""

import sys
from base64 import b64decode
from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from karta.config import Config
from karta.fs import read_file, resolve_safe_path


# Embedded favicon (64x64 PNG, ~1.9KB alpaca icon)
_FAVICON = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAHPElEQVR42u1aS2gT3Re/d2aaNo9O"
    "YqI1rXQCDcaFaBM0PmK0UhBRwYUghVqKC3etGxUp4gOKmy7UjRsV3VjEEhTaRUHRaONGBRGzscUu"
    "jJRYta+01pp53W9x/sx/yGO+zGRSPyF3EZLJ3DPnd97n3MOEEPQ3Lwr95asKoAqgCuAvX4zpFAkh"
    "siwTQiiKoigKISTLsizLGGOapk1/HDY3D0iSpM3lv97wxwAQQkDqhJAXL148ffr0w4cPs7OzGOO1"
    "a9eGQqGDBw/u3bsXFIIxxhgjEx9c5pIkCb7EYrHt27cXe1YkEhkZGcnZUuYyAYAoioSQ+fn5zs7O"
    "/0UGimIYhqZpcAOaphmGUUTe3d2dyWTMwoBMkf3nz59bW1sRQsB0MQ3QNA0OEAqFUqmUKRhQ+dyn"
    "0+lAIIAQYpiSYlpNTQ1CaNOmTel0unwMxgHIsiyKYjabjUQiCvfarqn4Lty8e/fubDYriiKE3dUG"
    "AKZ/+vTpHO6LYci5Dlt6e3sVUqsKAB758uXLHMtZs2aNBga73a6+Gb4/f/68HAzIsPWLohgOh9WO"
    "u3PnzoWFhZMnTwJzkHoxxgzDUBTV2NiYSqWuXbsGW5TPUCgkCIIkScYMyQgAQRAIIUNDQwoTIMuB"
    "gYGJiYmfP39u2LAhX/zDw8PT09OJRMJutytagu2Dg4MK2dUAIMuyJEnhcFgpb+Dz8ePHBw4cSCQS"
    "N2/e3LhxY1dX15kzZ3p6esLhcFtbmyiKO3bsePLkic/nUwPAGAeDQcOujIxZ/6tXryBhqa05Fot1"
    "dXVt27aN5/mZmZnl5WVAu7i4mMlkbt26ZbVaP3786HQ61X4CROLxuDFPMFhO379/Xw0A1vj4eFtb"
    "2+TkpCzLHo/HZrNJkoQxttvtLMu+efOmtbWV5/lMJoPx/2swIAIEK14LgZaXl5ebm5vVAOBLMBhM"
    "JpO3b98GN4ebIV3IshyPx0dGRvr7+3MCF+xtampaWlpSHlEpEwIVj42N5Ysffj58+LCgJQBbc3Nz"
    "4N85cbYcK6L0qgshlEgk8gHAlUwmo4hfvUsURVEUl5aWClZKcBHkore819eRwZPevn2b/ySKokRR"
    "nJubUyo2QoiSm6H+gaI1P80BKSCrUQuWCwD6FUEQxsfH8wGAyBOJxOHDh5PJ5L59+ziOk2UZtsRi"
    "sebm5mQyyfN8/l74OTExwfO8xWJRkJvsxFA2Tk1N2Ww2jXqhsbERaopnz54JgjA7O9ve3o4QcrlcoIf8"
    "jXDFarV++fJFb31K6XWAb9++/fr1Sx0H1VaEMT5//rzT6Vy/fv3+/fsZhnG73UeOHEEIXbx4EerW"
    "giaEMV5ZWZmenq74WGVmZqaY+EEku3btamlpOXXq1OvXr0+cODE0NNTd3e12u6PRaFNTU7G9cBGI"
    "6/JjRq8G5ufni5kBIYRhmIaGhrGxMZvN1t/f/+DBg9ra2o6Ojvfv33Mc53K5tAEsLCzoBaBbA4Ig"
    "aPzLsizLsvX19TRNX758ec+ePdevX0cIcRxHCOE4TqPXQQiBi1d2sFVMPKABj8fjcrkIITzPf//+"
    "PRAIpNNpjLHD4aBp2uv1GiNuJgDtsRTLsgzDyLJM0/SFCxcGBwcnJydHR0dBwBC+CnIJF0vsqg0C"
    "ACagmi+2fv/+rbBy9uzZurq6jo4Oh8MBAR7CqMbSJm6OBjwej5K28hdUMjCfCwaDd+7cUeutrq5O"
    "WwNAXNfQjtKrgXXr1tE0XSxZ1tbWQi2AMVbq0JwmuCBlyNkNDQ0VB+D1ekFOGsWSej5Xem3j8Xgg"
    "i1cQACHE6XSqe0I1rwzDWCwWDQrFDA9I+Xw+p9OprxDSmwckSUIIbdmyRS1sMACe56Fg1oiG2Wy2"
    "oICBFAwn4RGVPeCIRCL37t0DLkEtLS0t7e3toij6/X5jXSFCKBqNVvyEBkQVjUZramoEQYCfbrc7"
    "Ho+DXRUcwmnnKYyxJEkWiwVOD/T2A5ReAISQQCCwdetWiCqyLPf19fl8vmw2K0lSMQMA1n/8+FGw"
    "n8QYh8Nhv98Psaiy1SgMGo4fPw5RPxAI9PT0gAiVXkwjzRWLDUCwmJebeUID3UYqlXI4HAihR48e"
    "ldKJw9RtYGAgJxvAvJpl2a9fvxobtet2YoqiJEniOO7QoUOfPn06duxY6ed2mUwmv7ISRbGzs9Pr"
    "9Ro7/zMShUDpV65cWVlZ0ZV3oNzPScBWq/XcuXN6w39ZAMDPNm/enJ99tbM4NFw54u/t7fX7/caP"
    "X8s5oSndZOFO6O6BUYDt9/sXFxcNz9aNz0ZBqKWHPIi/SssLvktR1N27d+vr6w3bj2nnxCVOVGGu"
    "CKeuCKEbN26Ueb5kzjlxiQCmpqbsdjuUfQihvr4+w4caqw0AHCCZTCoZ4OrVqyD7cs4nVw8AGMno"
    "6Ch47fDwcPmWY4ITG3D6S5cuvXv37ujRoya+s2Ly6zamvJJT2WKuTNYJIf/R94X+1Kq+9FcFUAVQ"
    "BfBn1z9UP8A9BkE2cAAAAABJRU5ErkJggg=="
)


# -- ANSI styling for request logs -----------------------------------------


def _log_styled(text: str, code: str) -> str:
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


def _status_color(status: int) -> str:
    """Return an ANSI-colored status code string.

    Args:
        status: HTTP status code.

    Returns:
        Color-coded status string (green for 2xx, yellow for 3xx, red for 4xx+).
    """
    text = str(status)
    if 200 <= status < 300:
        return _log_styled(text, "32")
    if 300 <= status < 400:
        return _log_styled(text, "33")
    return _log_styled(text, "31")


# -- Request handler -------------------------------------------------------


class KartaHandler(BaseHTTPRequestHandler):
    """HTTP request handler that serves files from a configured directory.

    Config is injected via ``functools.partial`` when creating the handler
    class, since ``HTTPServer`` instantiates the handler per-request.
    """

    def __init__(
        self,
        config: Config,
        request: Any,
        client_address: Any,
        server: HTTPServer,
    ) -> None:
        """Initialize handler with injected config.

        Args:
            config: The resolved server configuration.
            request: The incoming socket request.
            client_address: The ``(host, port)`` of the client.
            server: The parent ``HTTPServer`` instance.
        """
        self.config = config
        super().__init__(request, client_address, server)

    def do_GET(self) -> None:
        """Handle GET requests: serve files, directory placeholders, or errors."""
        if self.path == "/favicon.ico":
            self._serve_favicon()
            return

        request_path = unquote(self.path)
        resolved = resolve_safe_path(self.config.directory, request_path)

        if resolved is None:
            self._send_error(403, "Forbidden")
            return

        if not resolved.exists():
            self._send_error(404, "Not Found")
            return

        if resolved.is_dir():
            self._serve_directory(request_path)
            return

        self._serve_file(resolved)

    def _serve_file(self, path: Path) -> None:
        """Serve a file with correct Content-Type and Content-Length.

        Args:
            path: Resolved filesystem path to the file.
        """
        content, content_type = read_file(path)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_directory(self, request_path: str) -> None:
        """Serve a placeholder response for directory requests.

        Args:
            request_path: The original URL path.
        """
        body = f"Directory: {request_path}".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_favicon(self) -> None:
        """Serve the embedded favicon without logging the request."""
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(_FAVICON)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(_FAVICON)

    def _send_error(self, code: int, message: str) -> None:
        """Send an error response with a plain-text body.

        Args:
            code: HTTP status code.
            message: Human-readable error message.
        """
        body = message.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_request(self, code: int | str = "-", size: int | str = 0) -> None:
        """Log a request with colored output to stderr.

        Favicon requests are suppressed to reduce log noise.

        Args:
            code: HTTP status code.
            size: Response size (unused, kept for API compatibility).
        """
        if self.path == "/favicon.ico":
            return
        method = _log_styled(self.command or "?", "1")
        path = _log_styled(self.path, "36")
        status = _status_color(int(code)) if str(code).isdigit() else str(code)
        print(f"  {method} {path} {status}", file=sys.stderr)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Suppress default BaseHTTPRequestHandler logging.

        All logging goes through ``log_request`` instead.

        Args:
            format: Printf-style format string (ignored).
            *args: Format arguments (ignored).
        """


# -- Server startup --------------------------------------------------------


def run_server(config: Config) -> None:
    """Start the HTTP server and block until interrupted.

    Creates an ``HTTPServer`` with ``KartaHandler`` configured via
    ``functools.partial``, then serves requests until ``KeyboardInterrupt``.

    Args:
        config: The resolved server configuration.
    """
    handler = partial(KartaHandler, config)
    server = HTTPServer((config.host, config.port), handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
