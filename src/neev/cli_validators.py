"""CLI argument validation and Config resolution for neev."""

import argparse
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from neev.cli_banner import _print_error, _print_warning
from neev.config import Config
from neev.share import generate_secret, parse_secret_hex


# Real defaults live here (not on the parser). The parser uses ``None`` as a
# sentinel so CLI-vs-TOML precedence can be resolved unambiguously: if an
# attribute is ``None`` after parsing, the user did not pass that flag, and
# TOML (or these defaults) may fill it in.
_DEFAULTS = {
    "host": "127.0.0.1",
    "port": 8000,
    "show_hidden": False,
    "enable_zip_download": False,
    "max_zip_size": 100,
    "enable_upload": False,
    "read_only": False,
}


def _parse_auth(auth_string: str) -> tuple[str, str]:
    """Split an ``user:pass`` string into username and password.

    Args:
        auth_string: Credentials in ``user:pass`` format.

    Returns:
        A ``(username, password)`` tuple.

    Raises:
        SystemExit: If the string does not contain exactly one colon.
    """
    if ":" not in auth_string:
        _print_error(f"invalid auth format '{auth_string}' — expected 'user:pass'")
        raise SystemExit(1)
    username, password = auth_string.split(":", maxsplit=1)
    return username, password


def _resolve_auth(args: argparse.Namespace) -> tuple[str | None, str | None]:
    """Resolve auth credentials from args (CLI flag or merged TOML value).

    Args:
        args: Parsed CLI arguments (post-TOML-merge).

    Returns:
        A ``(username, password)`` tuple, or ``(None, None)`` if no auth is configured.
    """
    if not args.auth:
        return None, None
    return _parse_auth(args.auth)


def _validate_public_url(raw: str) -> str:
    """Validate a public URL and strip any trailing slash.

    Accepts ``http://`` or ``https://`` URLs with a non-empty host. An
    optional path is allowed (for subpath mounts behind a proxy); query
    strings and fragments are rejected as they don't make sense as a
    base URL.

    Args:
        raw: The user-supplied URL string.

    Returns:
        The validated URL with any trailing slash stripped.

    Raises:
        SystemExit: If the URL is invalid.
    """
    candidate = raw.strip()
    if not candidate:
        _print_error("--public-url cannot be empty")
        raise SystemExit(1)
    try:
        parsed = urlparse(candidate)
    except ValueError:
        _print_error(f"invalid --public-url '{raw}'")
        raise SystemExit(1) from None
    if parsed.scheme not in ("http", "https"):
        _print_error(f"--public-url must start with http:// or https:// (got '{raw}')")
        raise SystemExit(1)
    if not parsed.netloc:
        _print_error(f"--public-url is missing a host (got '{raw}')")
        raise SystemExit(1)
    if parsed.query or parsed.fragment:
        _print_error(f"--public-url must not contain a query or fragment (got '{raw}')")
        raise SystemExit(1)
    return candidate.rstrip("/")


def _resolve_share_secret(args: argparse.Namespace) -> bytes:
    """Resolve the server's share-link HMAC secret.

    If ``share-secret`` was set via TOML, decode it from hex. Otherwise
    generate a fresh one and print it to stderr so the operator can pin
    it in ``neev.toml`` if they want tokens to survive a restart.

    Args:
        args: Parsed CLI arguments (post-TOML-merge).

    Returns:
        The secret bytes.

    Raises:
        SystemExit: If a configured ``share-secret`` is not valid hex.
    """
    raw = getattr(args, "share_secret", None)
    if raw is None:
        generated = generate_secret()
        _print_warning(
            f"no share-secret configured; generated ephemeral one: {generated.hex()} "
            '(pin it in neev.toml as share-secret = "..." to survive restarts)'
        )
        return generated
    if not isinstance(raw, str):
        _print_error("share-secret in neev.toml must be a hex-encoded string")
        raise SystemExit(1)
    try:
        return parse_secret_hex(raw)
    except ValueError as exc:
        _print_error(str(exc))
        raise SystemExit(1) from None


def _resolve_public_url(args: argparse.Namespace) -> str | None:
    """Resolve the public URL from args, or return ``None`` if unset.

    Args:
        args: Parsed CLI arguments (post-TOML-merge).

    Returns:
        The validated URL, or ``None`` if unset.
    """
    if not args.public_url:
        return None
    return _validate_public_url(args.public_url)


def _validate_directory(directory: Path) -> Path:
    """Resolve and validate the served directory.

    Args:
        directory: Path provided by the user (may be relative).

    Returns:
        The resolved absolute path.

    Raises:
        SystemExit: If the directory does not exist or is not a directory.
    """
    resolved = directory.resolve()
    if not resolved.exists():
        _print_error(f"directory '{directory}' does not exist")
        raise SystemExit(1)
    if not resolved.is_dir():
        _print_error(f"'{directory}' is not a directory")
        raise SystemExit(1)
    return resolved


def _validate_port(value: str) -> int:
    """Validate and convert a port string to an integer.

    Args:
        value: The raw string from argparse.

    Returns:
        The port number as an integer.

    Raises:
        argparse.ArgumentTypeError: If the value is not a valid port (1-65535).
    """
    try:
        port = int(value)
    except ValueError:
        msg = f"'{value}' is not a valid port number"
        raise argparse.ArgumentTypeError(msg) from None
    if port < 1 or port > 65535:
        msg = f"port must be between 1 and 65535, got {port}"
        raise argparse.ArgumentTypeError(msg)
    return port


def _resolve(args: argparse.Namespace, attr: str) -> Any:
    """Return ``args.<attr>`` if set, otherwise the registered default."""
    value = getattr(args, attr)
    if value is None:
        return _DEFAULTS[attr]
    return value


def build_config(args: argparse.Namespace, directory: Path) -> Config:
    """Resolve and validate parsed CLI arguments into a ``Config``.

    Applies real defaults to any attribute still set to ``None`` after TOML
    merging, resolves auth, and enforces ``--read-only``.

    Args:
        args: Parsed CLI arguments (post-TOML-merge).
        directory: The validated, resolved directory to serve.

    Returns:
        A frozen ``Config`` instance ready for use by the server.
    """
    username, password = _resolve_auth(args)

    max_zip_size = _resolve(args, "max_zip_size")
    if max_zip_size < 1:
        _print_error("--max-zip-size must be at least 1 MB")
        raise SystemExit(1)

    enable_upload = _resolve(args, "enable_upload")
    if _resolve(args, "read_only"):
        enable_upload = False

    return Config(
        directory=directory,
        host=_resolve(args, "host"),
        port=_resolve(args, "port"),
        username=username,
        password=password,
        show_hidden=_resolve(args, "show_hidden"),
        enable_zip_download=_resolve(args, "enable_zip_download"),
        max_zip_size=max_zip_size * 1024 * 1024,
        enable_upload=enable_upload,
        banner=args.banner,
        public_url=_resolve_public_url(args),
        share_secret=_resolve_share_secret(args),
    )
