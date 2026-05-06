"""Terminal output helpers for the neev CLI: startup banner and errors."""

import sys
from pathlib import Path

from neev.config import Config
from neev.log import ansi_styled


def _print_error(message: str) -> None:
    """Print a red error message to stderr.

    Args:
        message: The error description (without ``error:`` prefix).
    """
    if sys.stderr.isatty():
        print(f"\033[31merror:\033[0m {message}", file=sys.stderr)
    else:
        print(f"error: {message}", file=sys.stderr)


def _print_warning(message: str) -> None:
    """Print a yellow warning message to stderr.

    Args:
        message: The warning text (without ``warning:`` prefix).
    """
    if sys.stderr.isatty():
        print(f"\033[33mwarning:\033[0m {message}", file=sys.stderr)
    else:
        print(f"warning: {message}", file=sys.stderr)


def _on(label: str) -> str:
    """Format an enabled feature label in green."""
    return ansi_styled(label, "32", stream=sys.stdout)


def _off(label: str) -> str:
    """Format a disabled feature label in dim gray."""
    return ansi_styled(label, "2", stream=sys.stdout)


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
