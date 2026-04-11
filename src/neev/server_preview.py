"""Preview page handlers for neev.

Serves HTML preview pages for markdown, images, text/code, PDF, and media files.
"""

import html
import json
from pathlib import Path
from typing import TYPE_CHECKING

from neev.html_markdown import render_markdown_preview
from neev.html_preview import (
    render_image_preview,
    render_media_preview,
    render_pdf_preview,
    render_text_preview,
)


if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _parent_url(request_path: str) -> str:
    """Compute the escaped parent directory URL from a request path."""
    raw = request_path.rsplit("/", maxsplit=1)[0] + "/" if "/" in request_path else "/"
    return html.escape(raw)


def serve_markdown_preview(
    handler: "BaseHTTPRequestHandler", path: Path, request_path: str
) -> None:
    """Serve an HTML page that renders a markdown file client-side.

    Args:
        handler: The HTTP request handler.
        path: Resolved filesystem path to the markdown file.
        request_path: The original URL path from the request.
    """
    filename = html.escape(path.name)
    raw_path = request_path.rstrip("/") + "?download"
    raw_url = html.escape(raw_path)
    raw_url_js = json.dumps(raw_path)
    parent = _parent_url(request_path)
    page = render_markdown_preview(filename, raw_url, raw_url_js, parent)
    body = page.encode()
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def serve_generic_preview(
    handler: "BaseHTTPRequestHandler",
    path: Path,
    request_path: str,
    mime_type: str,
) -> None:
    """Serve an HTML preview page for images, text, PDF, or media.

    Args:
        handler: The HTTP request handler.
        path: Resolved filesystem path to the file.
        request_path: The original URL path from the request.
        mime_type: The detected MIME type of the file.
    """
    filename = html.escape(path.name)
    raw_path = request_path.rstrip("/")
    raw_url = html.escape(raw_path)
    download_url = html.escape(raw_path + "?download")
    parent = _parent_url(request_path)

    if mime_type.startswith("image/"):
        page = render_image_preview(filename, raw_url, parent, download_url)
    elif mime_type == "application/pdf":
        page = render_pdf_preview(filename, raw_url, parent, download_url)
    elif mime_type.startswith(("video/", "audio/")):
        page = render_media_preview(filename, raw_url, parent, download_url, mime_type)
    else:
        raw_url_js = json.dumps(raw_path)
        page = render_text_preview(filename, raw_url_js, parent, download_url)

    body = page.encode()
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)
