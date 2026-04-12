"""Tests for user-level neev.toml and the flags > local > user precedence chain."""

import types
from pathlib import Path
from unittest.mock import patch

import pytest

from neev.cli import main
from neev.toml_config import load_user_toml, user_config_path


@pytest.fixture
def user_home(tmp_path, monkeypatch):
    """Point ``Path.home()`` and XDG/APPDATA at a temp dir so tests don't touch the real home."""
    monkeypatch.setattr("neev.toml_config.Path.home", lambda: tmp_path)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("APPDATA", raising=False)
    return tmp_path


class TestUserConfigPath:
    def test_xdg_config_home_preferred(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        path = user_config_path()
        assert path == tmp_path / "xdg" / "neev" / "neev.toml"

    def test_default_to_dot_config(self, user_home):
        path = user_config_path()
        assert path == user_home / ".config" / "neev" / "neev.toml"

    def test_windows_uses_appdata(self, monkeypatch):
        """Simulate Windows by swapping the module's ``os`` reference for a stub.

        We can't set ``os.name = 'nt'`` globally — pathlib would try to
        instantiate ``WindowsPath`` on Linux and crash. Patching only the
        local module's ``os`` binding keeps pathlib untouched.
        """
        fake_os = types.SimpleNamespace(
            name="nt",
            environ={"APPDATA": "/fake/AppData/Roaming"},
        )
        monkeypatch.setattr("neev.toml_config.os", fake_os)
        path = user_config_path()
        assert path == Path("/fake/AppData/Roaming/neev/neev.toml")


class TestLoadUserToml:
    def test_missing_is_empty(self, user_home):
        assert load_user_toml() == {}

    def test_loads_when_present(self, user_home):
        cfg_dir = user_home / ".config" / "neev"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "neev.toml").write_text('port = 7070\nbanner = "user"\n')
        data = load_user_toml()
        assert data["port"] == 7070
        assert data["banner"] == "user"

    def test_malformed_logs_warning_no_crash(self, user_home, caplog):
        cfg_dir = user_home / ".config" / "neev"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "neev.toml").write_text("not valid [[[ toml")
        assert load_user_toml() == {}
        assert any("failed to read" in r.message for r in caplog.records)

    def test_denied_directory_key_ignored(self, user_home, tmp_path, caplog):
        """A ``directory`` key in user toml must never override the served dir."""
        cfg_dir = user_home / ".config" / "neev"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "neev.toml").write_text('directory = "/etc"\nport = 7070\n')
        served = tmp_path / "served"
        served.mkdir()
        with (
            patch("sys.argv", ["neev", str(served)]),
            patch("neev.cli.run_server") as mock_server,
        ):
            main()
        config = mock_server.call_args[0][0]
        assert config.directory == served.resolve()
        assert config.port == 7070
        assert any("denied" in r.message.lower() for r in caplog.records)


class TestPrecedence:
    """Flags > local neev.toml > user neev.toml > hardcoded defaults."""

    def _write_user(self, user_home, content):
        cfg_dir = user_home / ".config" / "neev"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "neev.toml").write_text(content)

    def test_user_config_fills_when_nothing_else_set(self, user_home, tmp_path):
        self._write_user(user_home, "port = 7070\n")
        served = tmp_path / "served"
        served.mkdir()
        with (
            patch("sys.argv", ["neev", str(served)]),
            patch("neev.cli.run_server") as mock_server,
        ):
            main()
        assert mock_server.call_args[0][0].port == 7070

    def test_local_beats_user(self, user_home, tmp_path):
        self._write_user(user_home, "port = 7070\n")
        served = tmp_path / "served"
        served.mkdir()
        (served / "neev.toml").write_text("port = 8080\n")
        with (
            patch("sys.argv", ["neev", str(served)]),
            patch("neev.cli.run_server") as mock_server,
        ):
            main()
        assert mock_server.call_args[0][0].port == 8080

    def test_flag_beats_local_beats_user(self, user_home, tmp_path):
        self._write_user(user_home, "port = 7070\n")
        served = tmp_path / "served"
        served.mkdir()
        (served / "neev.toml").write_text("port = 8080\n")
        with (
            patch("sys.argv", ["neev", str(served), "--port", "9000"]),
            patch("neev.cli.run_server") as mock_server,
        ):
            main()
        assert mock_server.call_args[0][0].port == 9000

    def test_user_auth_applied(self, user_home, tmp_path):
        """Per-user credentials are the intended replacement for NEEV_AUTH."""
        self._write_user(user_home, 'auth = "alice:s3cret"\n')
        served = tmp_path / "served"
        served.mkdir()
        with (
            patch("sys.argv", ["neev", str(served)]),
            patch("neev.cli.run_server") as mock_server,
        ):
            main()
        config = mock_server.call_args[0][0]
        assert config.username == "alice"
        assert config.password == "s3cret"

    def test_banner_lists_loaded_configs(self, user_home, tmp_path, capsys):
        self._write_user(user_home, "port = 7070\n")
        served = tmp_path / "served"
        served.mkdir()
        (served / "neev.toml").write_text('banner = "hello"\n')
        with (
            patch("sys.argv", ["neev", str(served)]),
            patch("neev.cli.run_server"),
        ):
            main()
        out = capsys.readouterr().out
        assert str(served / "neev.toml") in out
        assert str(user_home / ".config" / "neev" / "neev.toml") in out
