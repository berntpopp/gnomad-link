"""Tests for the command line interface."""

from argparse import Namespace
from unittest.mock import Mock, patch

import httpx
import pytest

from gnomad_link.cli import handle_health_command


def test_health_command_reports_healthy_server(capsys: pytest.CaptureFixture[str]) -> None:
    """Health command reports the transport and status from a healthy server."""
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"status": "healthy", "transport": "unified"}

    with patch("gnomad_link.cli.httpx.get", return_value=response) as mock_get:
        handle_health_command(Namespace(url="http://127.0.0.1:8000"))

    mock_get.assert_called_once_with("http://127.0.0.1:8000/health", timeout=5)
    output = capsys.readouterr().out
    assert "Server is healthy" in output
    assert "Transport: unified" in output
    assert "Status: healthy" in output


def test_health_command_exits_for_connection_error() -> None:
    """Health command exits with status 1 when the server cannot be reached."""
    with patch("gnomad_link.cli.httpx.get", side_effect=httpx.ConnectError("offline")):
        with pytest.raises(SystemExit) as exc_info:
            handle_health_command(Namespace(url="http://127.0.0.1:8000"))

    assert exc_info.value.code == 1
