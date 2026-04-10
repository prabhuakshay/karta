from unittest.mock import patch

from karta import main


class TestMainEntryPoint:
    def test_delegates_to_cli_main(self):
        with patch("karta.cli_main") as mock_cli_main:
            main()
        mock_cli_main.assert_called_once()
