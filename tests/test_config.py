from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from neev.config import Config


@pytest.fixture
def sample_config():
    return Config(
        directory=Path("/tmp"),
        host="127.0.0.1",
        port=8000,
        username=None,
        password=None,
        show_hidden=False,
        enable_zip_download=False,
        max_zip_size=104857600,
        enable_upload=False,
    )


class TestConfigCreation:
    def test_all_fields_stored(self, sample_config):
        assert sample_config.directory == Path("/tmp")
        assert sample_config.host == "127.0.0.1"
        assert sample_config.port == 8000
        assert sample_config.username is None
        assert sample_config.password is None
        assert sample_config.show_hidden is False
        assert sample_config.enable_zip_download is False
        assert sample_config.max_zip_size == 104857600
        assert sample_config.enable_upload is False

    def test_with_auth(self):
        config = Config(
            directory=Path("/srv"),
            host="0.0.0.0",
            port=9000,
            username="alice",
            password="secret",
            show_hidden=True,
            enable_zip_download=True,
            max_zip_size=209715200,
            enable_upload=True,
        )
        assert config.username == "alice"
        assert config.password == "secret"
        assert config.show_hidden is True
        assert config.enable_zip_download is True
        assert config.enable_upload is True


class TestConfigFrozen:
    def test_cannot_modify_field(self, sample_config):
        with pytest.raises(FrozenInstanceError):
            sample_config.host = "0.0.0.0"  # type: ignore[misc]

    def test_cannot_modify_port(self, sample_config):
        with pytest.raises(FrozenInstanceError):
            sample_config.port = 9999  # type: ignore[misc]
