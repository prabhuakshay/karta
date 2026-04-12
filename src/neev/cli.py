"""CLI argument parsing and entry point for neev."""

import argparse
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from neev.config import Config
from neev.log import ansi_styled
from neev.server import run_server
from neev.toml_config import (
    TOML_FILENAME,
    load_toml,
    load_user_toml,
    merge_toml_into_args,
    user_config_path,
)


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


def _print_error(message: str) -> None:
    """Print a red error message to stderr.

    Args:
        message: The error description (without ``error:`` prefix).
    """
    if sys.stderr.isatty():
        print(f"\033[31merror:\033[0m {message}", file=sys.stderr)
    else:
        print(f"error: {message}", file=sys.stderr)


def _on(label: str) -> str:
    """Format an enabled feature label in green."""
    return ansi_styled(label, "32", stream=sys.stdout)


def _off(label: str) -> str:
    """Format a disabled feature label in dim gray."""
    return ansi_styled(label, "2", stream=sys.stdout)


# -- Parsing and validation ------------------------------------------------


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


def _build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser with all neev CLI flags.

    All optional flags default to ``None`` so a caller can distinguish "not
    passed" from "passed with a value that happens to match the default".
    Real defaults are applied in :func:`build_config` after TOML merging.

    Returns:
        A configured ``ArgumentParser``.
    """
    parser = argparse.ArgumentParser(
        prog="neev",
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
        default=None,
        help="bind address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        "-p",
        default=None,
        type=_validate_port,
        help="bind port (default: 8000)",
    )
    parser.add_argument(
        "--auth",
        default=None,
        help="credentials as 'user:pass'",
    )
    parser.add_argument(
        "--show-hidden",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="show dotfiles, dotdirs, and neev.toml in listings",
    )
    parser.add_argument(
        "--enable-zip-download",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="allow ZIP downloads of folders",
    )
    parser.add_argument(
        "--max-zip-size",
        default=None,
        type=int,
        help="maximum ZIP archive size in MB (default: 100)",
    )
    parser.add_argument(
        "--enable-upload",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="allow file uploads",
    )
    parser.add_argument(
        "--read-only",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="disable all write operations (overrides --enable-upload)",
    )
    parser.add_argument(
        "--banner",
        default=None,
        help="message to display at the top of directory listings",
    )
    parser.add_argument(
        "--public-url",
        default=None,
        help="external base URL for neev behind a reverse proxy",
    )
    return parser


def _print_startup_banner(config: Config, loaded_configs: list[Path] | None = None) -> None:
    """Print a human-readable summary of the resolved configuration.

    Args:
        config: The resolved server configuration.
        loaded_configs: Paths of any ``neev.toml`` files that contributed
            values, in precedence order (local before user).
    """
    bind_url = f"http://{config.host}:{config.port}"
    directory = ansi_styled(str(config.directory), "1", stream=sys.stdout)
    serving = ansi_styled("Serving", "1;36", stream=sys.stdout)

    auth_status = _on(f"enabled (user: {config.username})") if config.username else _off("disabled")
    upload_status = _on("enabled") if config.enable_upload else _off("disabled")
    zip_status = _on("enabled") if config.enable_zip_download else _off("disabled")
    hidden_status = _on("visible") if config.show_hidden else _off("hidden")

    print(f"{serving} {directory}")
    if config.public_url and config.public_url != bind_url:
        public = ansi_styled(config.public_url, "1;36", stream=sys.stdout)
        bound = ansi_styled(f"(bound to {bind_url})", "2", stream=sys.stdout)
        print(f"  {public}")
        print(f"  {bound}")
    else:
        print(f"  {ansi_styled(bind_url, '1;36', stream=sys.stdout)}")
    print()
    print(f"  auth:          {auth_status}")
    print(f"  uploads:       {upload_status}")
    print(f"  zip downloads: {zip_status}")
    print(f"  hidden files:  {hidden_status}")
    if config.banner:
        print(f"  banner:        {_on(config.banner)}")
    if loaded_configs:
        paths = ", ".join(str(p) for p in loaded_configs)
        print(f"  config:        {ansi_styled(paths, '2', stream=sys.stdout)}")


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
    )


def main() -> None:
    """Entry point for the neev CLI.

    Config precedence (highest wins): CLI flags, then local ``neev.toml``
    in the served directory, then user-level ``neev.toml`` in the platform
    config dir, then hardcoded defaults.
    """
    parser = _build_parser()
    args = parser.parse_args()
    directory = _validate_directory(args.directory)

    loaded: list[Path] = []
    local_data = load_toml(directory)
    if local_data:
        merge_toml_into_args(args, local_data)
        loaded.append(directory / TOML_FILENAME)
    user_data = load_user_toml()
    if user_data:
        merge_toml_into_args(args, user_data)
        loaded.append(user_config_path())

    config = build_config(args, directory)
    _print_startup_banner(config, loaded)
    run_server(config)
