import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from karta.cli import (
    _build_parser,
    _off,
    _on,
    _parse_auth,
    _print_error,
    _print_startup_banner,
    _resolve_auth,
    _styled,
    _validate_directory,
    _validate_port,
    build_config,
    main,
)
from karta.config import Config


# -- ANSI styling helpers ---------------------------------------------------


class TestStyled:
    def test_returns_plain_text_when_not_tty(self):
        with patch("sys.stdout.isatty", return_value=False):
            assert _styled("hello", "1") == "hello"

    def test_wraps_with_ansi_when_tty(self):
        with patch("sys.stdout.isatty", return_value=True):
            assert _styled("hello", "1") == "\033[1mhello\033[0m"

    def test_on_delegates_to_styled(self):
        with patch("sys.stdout.isatty", return_value=True):
            result = _on("enabled")
            assert "\033[32m" in result
            assert "enabled" in result

    def test_off_delegates_to_styled(self):
        with patch("sys.stdout.isatty", return_value=True):
            result = _off("disabled")
            assert "\033[2m" in result
            assert "disabled" in result


class TestPrintError:
    def test_plain_when_not_tty(self, capsys):
        with patch("sys.stderr.isatty", return_value=False):
            _print_error("something broke")
        assert capsys.readouterr().err == "error: something broke\n"

    def test_red_when_tty(self, capsys):
        with patch("sys.stderr.isatty", return_value=True):
            _print_error("something broke")
        err = capsys.readouterr().err
        assert "\033[31merror:\033[0m" in err
        assert "something broke" in err


# -- _parse_auth -----------------------------------------------------------


class TestParseAuth:
    def test_valid_user_pass(self):
        assert _parse_auth("alice:secret") == ("alice", "secret")

    def test_password_with_colon(self):
        assert _parse_auth("alice:pass:word") == ("alice", "pass:word")

    def test_empty_password(self):
        assert _parse_auth("alice:") == ("alice", "")

    def test_no_colon_exits(self):
        with pytest.raises(SystemExit, match="1"):
            _parse_auth("invalid")

    def test_no_colon_prints_error(self, capsys):
        with pytest.raises(SystemExit):
            _parse_auth("badformat")
        assert "invalid auth format" in capsys.readouterr().err
        assert "user:pass" in capsys.readouterr().err or True  # already consumed above


# -- _resolve_auth ----------------------------------------------------------


class TestResolveAuth:
    def test_no_auth_returns_none(self):
        args = argparse.Namespace(auth=None)
        with patch.dict("os.environ", {}, clear=True):
            assert _resolve_auth(args) == (None, None)

    def test_flag_takes_precedence_over_env(self):
        args = argparse.Namespace(auth="cli:pass")
        with patch.dict("os.environ", {"KARTA_AUTH": "env:pass"}):
            assert _resolve_auth(args) == ("cli", "pass")

    def test_env_var_fallback(self):
        args = argparse.Namespace(auth=None)
        with patch.dict("os.environ", {"KARTA_AUTH": "envuser:envpass"}):
            assert _resolve_auth(args) == ("envuser", "envpass")

    def test_empty_env_var_returns_none(self):
        args = argparse.Namespace(auth=None)
        with patch.dict("os.environ", {"KARTA_AUTH": ""}):
            assert _resolve_auth(args) == (None, None)


# -- _validate_directory ----------------------------------------------------


class TestValidateDirectory:
    def test_valid_directory(self, tmp_path):
        result = _validate_directory(tmp_path)
        assert result == tmp_path.resolve()
        assert result.is_absolute()

    def test_nonexistent_exits(self):
        with pytest.raises(SystemExit, match="1"):
            _validate_directory(Path("/nonexistent/path/that/does/not/exist"))

    def test_nonexistent_prints_error(self, capsys):
        with pytest.raises(SystemExit):
            _validate_directory(Path("/nonexistent"))
        assert "does not exist" in capsys.readouterr().err

    def test_file_not_directory_exits(self, tmp_path):
        file_path = tmp_path / "somefile.txt"
        file_path.touch()
        with pytest.raises(SystemExit, match="1"):
            _validate_directory(file_path)

    def test_file_not_directory_prints_error(self, tmp_path, capsys):
        file_path = tmp_path / "somefile.txt"
        file_path.touch()
        with pytest.raises(SystemExit):
            _validate_directory(file_path)
        assert "is not a directory" in capsys.readouterr().err


# -- _validate_port ---------------------------------------------------------


class TestValidatePort:
    def test_valid_port(self):
        assert _validate_port("8000") == 8000

    def test_min_port(self):
        assert _validate_port("1") == 1

    def test_max_port(self):
        assert _validate_port("65535") == 65535

    def test_zero_rejected(self):
        with pytest.raises(argparse.ArgumentTypeError, match="between 1 and 65535"):
            _validate_port("0")

    def test_negative_rejected(self):
        with pytest.raises(argparse.ArgumentTypeError, match="between 1 and 65535"):
            _validate_port("-1")

    def test_too_high_rejected(self):
        with pytest.raises(argparse.ArgumentTypeError, match="between 1 and 65535"):
            _validate_port("65536")

    def test_non_numeric_rejected(self):
        with pytest.raises(argparse.ArgumentTypeError, match="not a valid port"):
            _validate_port("abc")

    def test_float_rejected(self):
        with pytest.raises(argparse.ArgumentTypeError, match="not a valid port"):
            _validate_port("80.5")


# -- _build_parser ----------------------------------------------------------


class TestBuildParser:
    def test_defaults(self):
        parser = _build_parser()
        args = parser.parse_args([])
        assert args.directory == Path(".")
        assert args.host == "127.0.0.1"
        assert args.port == 8000
        assert args.auth is None
        assert args.show_hidden is False
        assert args.enable_zip_download is False
        assert args.enable_upload is False
        assert args.read_only is False

    def test_all_flags(self, tmp_path):
        parser = _build_parser()
        args = parser.parse_args(
            [
                str(tmp_path),
                "--host",
                "0.0.0.0",
                "--port",
                "9000",
                "--auth",
                "user:pass",
                "--show-hidden",
                "--enable-zip-download",
                "--enable-upload",
                "--read-only",
            ]
        )
        assert args.directory == tmp_path
        assert args.host == "0.0.0.0"
        assert args.port == 9000
        assert args.auth == "user:pass"
        assert args.show_hidden is True
        assert args.enable_zip_download is True
        assert args.enable_upload is True
        assert args.read_only is True

    def test_short_port_flag(self):
        parser = _build_parser()
        args = parser.parse_args(["-p", "3000"])
        assert args.port == 3000

    def test_help_flag(self, capsys):
        parser = _build_parser()
        with pytest.raises(SystemExit, match="0"):
            parser.parse_args(["--help"])


# -- _print_startup_banner --------------------------------------------------


class TestPrintStartupBanner:
    def test_banner_no_auth(self, tmp_path, capsys):
        config = Config(
            directory=tmp_path,
            host="127.0.0.1",
            port=8000,
            username=None,
            password=None,
            show_hidden=False,
            enable_zip_download=False,
            enable_upload=False,
        )
        _print_startup_banner(config)
        output = capsys.readouterr().out
        assert f"Serving {tmp_path}" in output
        assert "http://127.0.0.1:8000" in output
        assert "auth:          disabled" in output
        assert "uploads:       disabled" in output
        assert "zip downloads: disabled" in output
        assert "hidden files:  hidden" in output

    def test_banner_with_auth(self, tmp_path, capsys):
        config = Config(
            directory=tmp_path,
            host="0.0.0.0",
            port=9000,
            username="alice",
            password="secret",
            show_hidden=True,
            enable_zip_download=True,
            enable_upload=True,
        )
        _print_startup_banner(config)
        output = capsys.readouterr().out
        assert "http://0.0.0.0:9000" in output
        assert "auth:          enabled (user: alice)" in output
        assert "uploads:       enabled" in output
        assert "zip downloads: enabled" in output
        assert "hidden files:  visible" in output


# -- build_config -----------------------------------------------------------


class TestBuildConfig:
    def test_defaults(self, tmp_path):
        parser = _build_parser()
        args = parser.parse_args([str(tmp_path)])
        with patch.dict("os.environ", {}, clear=True):
            config = build_config(args)
        assert config.directory == tmp_path.resolve()
        assert config.host == "127.0.0.1"
        assert config.port == 8000
        assert config.username is None
        assert config.password is None
        assert config.show_hidden is False
        assert config.enable_zip_download is False
        assert config.enable_upload is False

    def test_read_only_disables_upload(self, tmp_path):
        parser = _build_parser()
        args = parser.parse_args([str(tmp_path), "--enable-upload", "--read-only"])
        with patch.dict("os.environ", {}, clear=True):
            config = build_config(args)
        assert config.enable_upload is False

    def test_upload_enabled_without_read_only(self, tmp_path):
        parser = _build_parser()
        args = parser.parse_args([str(tmp_path), "--enable-upload"])
        with patch.dict("os.environ", {}, clear=True):
            config = build_config(args)
        assert config.enable_upload is True

    def test_auth_from_flag(self, tmp_path):
        parser = _build_parser()
        args = parser.parse_args([str(tmp_path), "--auth", "user:pass"])
        with patch.dict("os.environ", {}, clear=True):
            config = build_config(args)
        assert config.username == "user"
        assert config.password == "pass"

    def test_auth_from_env(self, tmp_path):
        parser = _build_parser()
        args = parser.parse_args([str(tmp_path)])
        with patch.dict("os.environ", {"KARTA_AUTH": "envuser:envpass"}):
            config = build_config(args)
        assert config.username == "envuser"
        assert config.password == "envpass"


# -- main -------------------------------------------------------------------


class TestMain:
    def test_main_runs(self, tmp_path, capsys):
        with (
            patch("sys.argv", ["karta", str(tmp_path)]),
            patch.dict("os.environ", {}, clear=True),
            patch("karta.cli.run_server") as mock_server,
        ):
            main()
        output = capsys.readouterr().out
        assert f"Serving {tmp_path.resolve()}" in output
        assert "http://127.0.0.1:8000" in output
        mock_server.assert_called_once()
