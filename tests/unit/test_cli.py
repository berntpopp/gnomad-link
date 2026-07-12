"""Tests for the typer command line interface (Standard v1)."""

from __future__ import annotations

from unittest.mock import Mock, patch

from typer.testing import CliRunner

from gnomad_link import __version__
from gnomad_link.cli import app

runner = CliRunner()


def test_no_args_shows_help() -> None:
    """Invoking with no arguments prints help and does not start a server."""
    result = runner.invoke(app, [])
    assert result.exit_code != 0  # no_args_is_help exits non-zero
    assert "serve" in result.output
    assert "config" in result.output
    assert "health" in result.output
    assert "version" in result.output


def test_version_command() -> None:
    """The version command prints the package version."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_serve_rejects_stdio_transport() -> None:
    """serve refuses the removed stdio transport with a usage error."""
    with patch("gnomad_link.server_manager.UnifiedServerManager") as mock_mgr:
        result = runner.invoke(app, ["serve", "--transport", "stdio"])
    assert result.exit_code == 2
    mock_mgr.assert_not_called()


def test_serve_accepts_unified_transport() -> None:
    """serve accepts the unified transport and starts the server manager."""
    with (
        patch("gnomad_link.server_manager.UnifiedServerManager") as mock_mgr,
        patch("gnomad_link.cli.asyncio.run") as mock_run,
    ):
        result = runner.invoke(app, ["serve", "--transport", "unified"])
    assert result.exit_code == 0
    mock_mgr.assert_called_once()
    mock_run.assert_called_once()


def test_serve_accepts_http_transport() -> None:
    """serve accepts the http transport and starts the server manager."""
    with (
        patch("gnomad_link.server_manager.UnifiedServerManager") as mock_mgr,
        patch("gnomad_link.cli.asyncio.run") as mock_run,
    ):
        result = runner.invoke(app, ["serve", "--transport", "http"])
    assert result.exit_code == 0
    mock_mgr.assert_called_once()
    mock_run.assert_called_once()


def test_serve_rejects_bad_mcp_path() -> None:
    """serve rejects an mcp-path that does not start with a slash."""
    result = runner.invoke(app, ["serve", "--mcp-path", "mcp"])
    assert result.exit_code == 2


def test_config_command_prints_settings() -> None:
    """config prints the resolved configuration table."""
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "transport" in result.output
    assert "log_format" in result.output


def test_config_validate_succeeds() -> None:
    """config --validate succeeds for the default valid configuration."""
    result = runner.invoke(app, ["config", "--validate"])
    assert result.exit_code == 0
    assert "valid" in result.output.lower()


def test_health_command_reports_healthy_server() -> None:
    """health reports the transport and status from a healthy server."""
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"status": "healthy", "transport": "unified"}

    with patch("gnomad_link.cli.httpx.get", return_value=response) as mock_get:
        result = runner.invoke(app, ["health", "--url", "http://127.0.0.1:8000"])

    mock_get.assert_called_once_with("http://127.0.0.1:8000/health", timeout=5)
    assert result.exit_code == 0
    assert "Server is healthy" in result.output
    assert "Transport: unified" in result.output


def test_health_command_exits_for_connection_error() -> None:
    """health exits non-zero when the server cannot be reached."""
    import httpx

    with patch("gnomad_link.cli.httpx.get", side_effect=httpx.ConnectError("offline")):
        result = runner.invoke(app, ["health"])

    assert result.exit_code == 1


def test_console_script_entry_point_resolves() -> None:
    """The console-script target gnomad_link.cli:app resolves to the typer app."""
    import importlib

    module = importlib.import_module("gnomad_link.cli")
    target = module.app
    assert target is app
    import typer

    assert isinstance(target, typer.Typer)


def test_serve_carries_configured_host_allowlist_into_server_config() -> None:
    """serve must hand the env-configured Host allowlist to the server manager.

    Regression: serve built ServerConfig(...) without allowed_hosts/allowed_origins, so
    the dataclass default (loopback only) silently overrode MCP_ALLOWED_HOSTS. Behind a
    reverse proxy the container then answered every proxied request -- and the
    genefoundry-router federating /mcp -- with HTTP 421, while `config --validate` still
    displayed the correct allowlist because it reads from_env(). Only `config` read the
    environment; the code path that actually serves did not.
    """
    public = "gnomad-link.genefoundry.org"

    with (
        patch("gnomad_link.config.settings.MCP_ALLOWED_HOSTS", ["localhost", public]),
        patch("gnomad_link.config.settings.MCP_ALLOWED_ORIGINS", [f"https://{public}"]),
        patch("gnomad_link.server_manager.UnifiedServerManager") as mock_mgr,
        patch("gnomad_link.cli.asyncio.run") as mock_run,
    ):
        result = runner.invoke(app, ["serve", "--transport", "unified"])

    assert result.exit_code == 0
    mock_run.assert_called_once()
    cfg = mock_mgr.return_value.start_server.call_args.args[0]
    assert public in cfg.allowed_hosts, (
        f"serve dropped the configured Host allowlist: {cfg.allowed_hosts}"
    )
    assert f"https://{public}" in cfg.allowed_origins
