"""CLI argument parsing and entry point for neev."""

import argparse
import sys
from pathlib import Path

from neev.cli_banner import _print_startup_banner
from neev.cli_share import is_share_invocation, share_main
from neev.cli_validators import _validate_directory, _validate_port, build_config
from neev.server import run_server
from neev.toml_config import (
    TOML_FILENAME,
    load_toml,
    load_user_toml,
    merge_toml_into_args,
    user_config_path,
)


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
    # share-secret is TOML-only (no CLI flag) but the attribute must exist
    # so merge_toml_into_args() can populate it without a spurious warning.
    parser.set_defaults(share_secret=None)
    return parser


def main() -> None:
    """Entry point for the neev CLI.

    Config precedence (highest wins): CLI flags, then local ``neev.toml``
    in the served directory, then user-level ``neev.toml`` in the platform
    config dir, then hardcoded defaults.
    """
    if is_share_invocation(sys.argv):
        share_main(sys.argv[2:])
        return

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
