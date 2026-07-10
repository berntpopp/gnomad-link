"""Host/Origin boundary contracts for the unified MCP application."""

from __future__ import annotations

import asyncio
from importlib.metadata import version
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from packaging.version import Version

from gnomad_link.config import ServerConfig, Settings
from gnomad_link.server_manager import UnifiedServerManager


def _build_client() -> TestClient:
    manager = UnifiedServerManager()
    manager.logger = MagicMock()
    config = ServerConfig(
        allowed_hosts=["localhost", "127.0.0.1", "::1", "gnomad-link.genefoundry.org"],
        allowed_origins=["https://genefoundry.org"],
    )
    app = asyncio.run(manager._create_unified_app(config))
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client() -> TestClient:
    return _build_client()


def test_fastmcp_344_strict_guard_is_installed(client: TestClient) -> None:
    assert Version(version("fastmcp")) >= Version("3.4.4")

    response = client.get("/mcp", headers={"Host": "gnomad-link.genefoundry.org"})
    assert response.status_code not in {403, 421}


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
def test_loopback_hosts_are_allowed(client: TestClient, host: str) -> None:
    response = client.get("/mcp", headers={"Host": host})
    assert response.status_code not in {403, 421}


@pytest.mark.parametrize("path", ["/health", "/mcp"])
def test_untrusted_host_is_rejected_on_every_route(client: TestClient, path: str) -> None:
    response = client.get(path, headers={"Host": "evil.example"})
    assert response.status_code == 421


def test_absent_and_configured_origins_are_allowed(client: TestClient) -> None:
    no_origin = client.get("/mcp", headers={"Host": "gnomad-link.genefoundry.org"})
    configured_origin = client.get(
        "/mcp",
        headers={
            "Host": "gnomad-link.genefoundry.org",
            "Origin": "https://genefoundry.org",
        },
    )
    assert no_origin.status_code not in {403, 421}
    assert configured_origin.status_code not in {403, 421}


@pytest.mark.parametrize("path", ["/health", "/mcp"])
def test_untrusted_origin_is_rejected_on_every_route(client: TestClient, path: str) -> None:
    response = client.get(
        path,
        headers={"Host": "gnomad-link.genefoundry.org", "Origin": "https://evil.example"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize("wildcard", ["*", "*.example.org", "host?.example.org", "host[0]"])
def test_wildcard_host_is_rejected(wildcard: str) -> None:
    with pytest.raises(ValueError, match="wildcard"):
        Settings(_env_file=None, MCP_ALLOWED_HOSTS=[wildcard])


def test_json_environment_allowlists_are_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "MCP_ALLOWED_HOSTS",
        '["localhost","gnomad-link.genefoundry.org"]',
    )
    monkeypatch.setenv("MCP_ALLOWED_ORIGINS", '["https://genefoundry.org"]')

    configured = Settings(_env_file=None)

    assert configured.MCP_ALLOWED_HOSTS == ["localhost", "gnomad-link.genefoundry.org"]
    assert configured.MCP_ALLOWED_ORIGINS == ["https://genefoundry.org"]
