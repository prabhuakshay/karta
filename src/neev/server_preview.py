"""Preview page handlers for neev.

Serves HTML preview pages for markdown, images, text/code, PDF, and media files.
"""

import html
from pathlib import Path
from typing import TYPE_CHECKING

from neev.fs import get_mime_type, is_previewable_type
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
    raw_url = html.escape(request_path.rstrip("/") + "?download")
    parent = _parent_url(request_path)
    page = render_markdown_preview(filename, raw_url, parent)
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
    raw_url = html.escape(request_path.rstrip("/"))
    download_url = html.escape(request_path.rstrip("/") + "?download")
    parent = _parent_url(request_path)

    if mime_type.startswith("image/"):
        page = render_image_preview(filename, raw_url, parent, download_url)
    elif mime_type == "application/pdf":
        page = render_pdf_preview(filename, raw_url, parent, download_url)
    elif mime_type.startswith(("video/", "audio/")):
        page = render_media_preview(filename, raw_url, parent, download_url, mime_type)
    else:
        page = render_text_preview(filename, raw_url, parent, download_url)

    body = page.encode()
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def is_generic_previewable(path: Path) -> bool:
    """Check whether a file should get a generic (non-markdown) preview.

    Args:
        path: Path to the file (only the name is used for MIME detection).

    Returns:
        ``True`` if the file's MIME type is previewable.
    """
    return is_previewable_type(get_mime_type(path))
