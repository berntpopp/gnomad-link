"""Host/Origin boundary contracts for the unified MCP application."""

from __future__ import annotations

import asyncio
import json
from importlib.metadata import version
from unittest.mock import MagicMock

import httpx
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
    assert Version(version("fastmcp")) >= Version("4.2.2")

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


_PUBLIC_HOST = "gnomad-link.genefoundry.org"
_PUBLIC_ORIGIN = "https://genefoundry.org"
_MODERN_VERSION = "2026-07-28"
_MODERN_META = {
    "io.modelcontextprotocol/protocolVersion": _MODERN_VERSION,
    "io.modelcontextprotocol/clientCapabilities": {},
    "io.modelcontextprotocol/clientInfo": {"name": "gnomad-host-test", "version": "1.0.0"},
}


def _modern_post(
    client: TestClient, req_id: int, method: str, params: dict[str, object], name: str | None = None
) -> httpx.Response:
    headers = {
        "Host": _PUBLIC_HOST,
        "Origin": _PUBLIC_ORIGIN,
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "mcp-protocol-version": _MODERN_VERSION,
        "mcp-method": method,
    }
    if name is not None:
        headers["mcp-name"] = name
    body = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": {"_meta": _MODERN_META, **params},
    }
    return client.post("/mcp", headers=headers, json=body)


def test_modern_mcp_http_discovers_lists_calls_and_fences_unknown_tool(client: TestClient) -> None:
    """The 2026-07-28 sessionless era (mcp-method / mcp-name headers) passes the
    Host/Origin guard end to end, and an unknown hostile tool is still fenced."""
    hostile = "ignore-instructions-secret"
    with client:
        discover = _modern_post(client, 1, "server/discover", {})
        listed = _modern_post(client, 2, "tools/list", {})
        called = _modern_post(
            client,
            3,
            "tools/call",
            {"name": "get_diagnostics", "arguments": {}},
            name="get_diagnostics",
        )
        unknown = _modern_post(
            client, 4, "tools/call", {"name": hostile, "arguments": {}}, name=hostile
        )

    assert discover.status_code == 200, discover.text
    assert _MODERN_VERSION in discover.json()["result"]["supportedVersions"]
    assert "mcp-session-id" not in discover.headers
    assert listed.status_code == 200, listed.text
    names = {tool["name"] for tool in listed.json()["result"]["tools"]}
    assert "get_diagnostics" in names
    assert called.status_code == 200, called.text
    called_result = called.json()["result"]
    assert called_result.get("isError") is not True, called_result
    assert unknown.status_code == 200, unknown.text
    unknown_result = unknown.json()["result"]
    assert unknown_result["isError"] is True
    assert json.loads(unknown_result["content"][0]["text"]) == unknown_result["structuredContent"]
    assert unknown_result["structuredContent"]["error_code"] == "not_found"
    assert hostile not in unknown.text
