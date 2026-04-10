"""CLI argument parsing and entry point for karta."""

import argparse
import os
import sys
from pathlib import Path

from karta.config import Config


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
        print(f"error: invalid auth format '{auth_string}' — expected 'user:pass'", file=sys.stderr)
        raise SystemExit(1)
    username, password = auth_string.split(":", maxsplit=1)
    return username, password


def _resolve_auth(args: argparse.Namespace) -> tuple[str | None, str | None]:
    """Resolve auth credentials from CLI flag or environment variable.

    ``--auth`` takes precedence over the ``KARTA_AUTH`` environment variable.

    Args:
        args: Parsed CLI arguments.

    Returns:
        A ``(username, password)`` tuple, or ``(None, None)`` if no auth is configured.
    """
    auth_string = args.auth or os.environ.get("KARTA_AUTH")
    if not auth_string:
        return None, None
    return _parse_auth(auth_string)


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
        print(f"error: directory '{directory}' does not exist", file=sys.stderr)
        raise SystemExit(1)
    if not resolved.is_dir():
        print(f"error: '{directory}' is not a directory", file=sys.stderr)
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


def _build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser with all karta CLI flags.

    Returns:
        A configured ``ArgumentParser``.
    """
    parser = argparse.ArgumentParser(
        prog="karta",
        description="Serve a local directory over HTTP with auth, file browsing, and downloads.",
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        type=Path,
        help="directory to serve (default: current directory)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="bind address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        "-p",
        default=8000,
        type=_validate_port,
        help="bind port (default: 8000)",
    )
    parser.add_argument(
        "--auth",
        default=None,
        help="credentials as 'user:pass' (or set KARTA_AUTH env var)",
    )
    parser.add_argument(
        "--show-hidden",
        action="store_true",
        default=False,
        help="show dotfiles and dotdirs in listings",
    )
    parser.add_argument(
        "--enable-zip-download",
        action="store_true",
        default=False,
        help="allow ZIP downloads of folders",
    )
    parser.add_argument(
        "--enable-upload",
        action="store_true",
        default=False,
        help="allow file uploads",
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        default=False,
        help="disable all write operations (overrides --enable-upload)",
    )
    return parser


def _print_startup_banner(config: Config) -> None:
    """Print a human-readable summary of the resolved configuration.

    Args:
        config: The resolved server configuration.
    """
    auth_status = f"enabled (user: {config.username})" if config.username else "disabled"
    features = []
    features.append(f"uploads: {'enabled' if config.enable_upload else 'disabled'}")
    features.append(f"zip downloads: {'enabled' if config.enable_zip_download else 'disabled'}")
    features.append(f"hidden files: {'visible' if config.show_hidden else 'hidden'}")

    print(f"Serving {config.directory} on http://{config.host}:{config.port}")
    print(f"  auth: {auth_status} | {' | '.join(features)}")


def build_config(args: argparse.Namespace) -> Config:
    """Resolve and validate parsed CLI arguments into a ``Config``.

    Handles auth resolution (flag vs env var), directory validation,
    and ``--read-only`` enforcement.

    Args:
        args: Parsed CLI arguments from argparse.

    Returns:
        A frozen ``Config`` instance ready for use by the server.
    """
    directory = _validate_directory(args.directory)
    username, password = _resolve_auth(args)

    enable_upload = args.enable_upload
    if args.read_only:
        enable_upload = False

    return Config(
        directory=directory,
        host=args.host,
        port=args.port,
        username=username,
        password=password,
        show_hidden=args.show_hidden,
        enable_zip_download=args.enable_zip_download,
        enable_upload=enable_upload,
    )


def main() -> None:
    """Entry point for the karta CLI."""
    parser = _build_parser()
    args = parser.parse_args()
    config = build_config(args)
    _print_startup_banner(config)
