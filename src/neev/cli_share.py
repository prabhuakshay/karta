"""Implementation of the ``neev share`` subcommand.

Generates a signed share URL for a path under the served directory.
The secret is resolved through the same config pipeline as the server
(local TOML → user TOML → auto-gen), so an operator who pins
``share-secret`` in ``neev.toml`` gets stable URLs across runs.
"""

import argparse
import sys
import time
from pathlib import Path

from neev.cli_banner import _print_error
from neev.cli_validators import _validate_directory, build_config
from neev.share import build_share_url, sign
from neev.toml_config import (
    load_toml,
    load_user_toml,
    merge_toml_into_args,
)


_DEFAULT_EXPIRES_SECONDS = 86400  # 24 hours


def _build_share_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neev share",
        description="Generate a signed, time-limited share URL for a file or folder.",
    )
    parser.add_argument(
        "path",
        type=Path,
        help="file or folder path to share (relative to the served directory or absolute)",
    )
    parser.add_argument(
        "-d",
        "--directory",
        default=".",
        type=Path,
        help="served directory (default: current directory)",
    )
    parser.add_argument(
        "--expires",
        type=int,
        default=_DEFAULT_EXPIRES_SECONDS,
        help=f"validity window in seconds (default: {_DEFAULT_EXPIRES_SECONDS})",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="allow POST/upload under this token (server must have uploads enabled)",
    )
    return parser


def _url_path_for(target: Path, served: Path) -> str:
    """Compute the URL path that corresponds to a filesystem target.

    Args:
        target: Real filesystem path to share.
        served: The served root directory.

    Returns:
        A leading-slash URL path rooted at the served directory.

    Raises:
        SystemExit: If ``target`` is not inside ``served`` or does not exist.
    """
    if not target.exists():
        _print_error(f"path does not exist: {target}")
        raise SystemExit(1)
    try:
        rel = target.resolve().relative_to(served)
    except ValueError:
        _print_error(f"path is not inside served directory {served}: {target}")
        raise SystemExit(1) from None
    rel_str = str(rel).replace("\\", "/")
    if rel_str in ("", "."):
        return "/"
    return "/" + rel_str


def _base_url(config_host: str, config_port: int, public_url: str | None) -> str:
    if public_url:
        return public_url
    host = "127.0.0.1" if config_host == "0.0.0.0" else config_host  # noqa: S104
    return f"http://{host}:{config_port}"


def share_main(argv: list[str]) -> None:
    """Entry point for ``neev share ...``.

    Args:
        argv: Arguments after the ``share`` subcommand (i.e. ``sys.argv[2:]``).
    """
    parser = _build_share_parser()
    args = parser.parse_args(argv)

    if args.expires < 1:
        _print_error("--expires must be at least 1 second")
        raise SystemExit(1)

    directory = _validate_directory(args.directory)

    # Reuse the server's config pipeline to pick up the secret (and
    # public_url, host, port) exactly as the running server would see it.
    server_parser = _build_server_parser_stub()
    server_args = server_parser.parse_args([str(directory)])
    local_data = load_toml(directory)
    if local_data:
        merge_toml_into_args(server_args, local_data)
    user_data = load_user_toml()
    if user_data:
        merge_toml_into_args(server_args, user_data)
    config = build_config(server_args, directory)

    target = args.path if args.path.is_absolute() else (directory / args.path).resolve()
    url_path = _url_path_for(target, directory)
    expires_at = int(time.time()) + args.expires
    token = sign(url_path, expires_at, args.write, config.share_secret or b"")
    base = _base_url(config.host, config.port, config.public_url)
    print(build_share_url(base, url_path, token))
    if not config.public_url:
        print(
            f"note: --public-url was not set; URL uses the bind host {config.host!r}. "
            "If clients connect from elsewhere, set public-url in neev.toml.",
            file=sys.stderr,
        )


def _build_server_parser_stub() -> argparse.ArgumentParser:
    """Build a minimal parser matching the main server's attribute surface.

    We import lazily here to avoid a circular import — cli.py's parser
    references helpers that already live under cli_validators.
    """
    from neev.cli import _build_parser  # noqa: PLC0415 -- deliberate lazy import

    return _build_parser()


def is_share_invocation(argv: list[str]) -> bool:
    """Return True when the user is running ``neev share ...``."""
    return len(argv) > 1 and argv[1] == "share"
