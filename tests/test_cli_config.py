"""Tests for CLI config building and main entry point."""

from unittest.mock import patch

from neev.cli import _build_parser, build_config, main


# -- build_config -----------------------------------------------------------


class TestBuildConfig:
    def test_defaults(self, tmp_path):
        parser = _build_parser()
        args = parser.parse_args([str(tmp_path)])
        with patch.dict("os.environ", {}, clear=True):
            config = build_config(args, tmp_path.resolve())
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
            config = build_config(args, tmp_path.resolve())
        assert config.enable_upload is False

    def test_upload_enabled_without_read_only(self, tmp_path):
        parser = _build_parser()
        args = parser.parse_args([str(tmp_path), "--enable-upload"])
        with patch.dict("os.environ", {}, clear=True):
            config = build_config(args, tmp_path.resolve())
        assert config.enable_upload is True

    def test_auth_from_flag(self, tmp_path):
        parser = _build_parser()
        args = parser.parse_args([str(tmp_path), "--auth", "user:pass"])
        with patch.dict("os.environ", {}, clear=True):
            config = build_config(args, tmp_path.resolve())
        assert config.username == "user"
        assert config.password == "pass"

    def test_auth_from_env(self, tmp_path):
        parser = _build_parser()
        args = parser.parse_args([str(tmp_path)])
        with patch.dict("os.environ", {"NEEV_AUTH": "envuser:envpass"}):
            config = build_config(args, tmp_path.resolve())
        assert config.username == "envuser"
        assert config.password == "envpass"


# -- main -------------------------------------------------------------------


class TestMain:
    def test_main_runs(self, tmp_path, capsys):
        with (
            patch("sys.argv", ["neev", str(tmp_path)]),
            patch.dict("os.environ", {}, clear=True),
            patch("neev.cli.run_server") as mock_server,
        ):
            main()
        output = capsys.readouterr().out
        assert f"Serving {tmp_path.resolve()}" in output
        assert "http://127.0.0.1:8000" in output
        mock_server.assert_called_once()
