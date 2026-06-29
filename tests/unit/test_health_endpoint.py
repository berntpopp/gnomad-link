"""Unit tests for /health endpoint — assert {status, version, transport}.

MCP Transport Standard v1 requires all three keys.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from gnomad_link.config import ServerConfig
from gnomad_link.server_manager import UnifiedServerManager


async def _build_app() -> TestClient:
    """Build a minimal FastAPI app via UnifiedServerManager._create_fastapi_app."""
    manager = UnifiedServerManager()
    manager.logger = MagicMock()
    manager._current_transport = "streamable-http-stateless"

    with patch.object(manager, "_create_frequency_service") as mock_svc:
        mock_svc.return_value = MagicMock(close=AsyncMock())
        config = ServerConfig(transport="unified")
        app = await manager._create_fastapi_app(config)

    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture(scope="module")
def client() -> TestClient:
    import asyncio

    return asyncio.run(_build_app())


def test_health_returns_200(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_has_status(client: TestClient) -> None:
    body = client.get("/health").json()
    assert "status" in body


def test_health_has_version(client: TestClient) -> None:
    """MCP Transport Standard v1: /health MUST include 'version'."""
    body = client.get("/health").json()
    assert "version" in body, f"Missing 'version' in /health response: {body}"


def test_health_has_transport(client: TestClient) -> None:
    """MCP Transport Standard v1: /health MUST include 'transport'."""
    body = client.get("/health").json()
    assert "transport" in body, f"Missing 'transport' in /health response: {body}"


def test_health_transport_value(client: TestClient) -> None:
    """transport MUST be 'streamable-http-stateless' for the stateless tier."""
    body = client.get("/health").json()
    assert body.get("transport") == "streamable-http-stateless", (
        f"Expected 'streamable-http-stateless', got {body.get('transport')!r}"
    )


def test_health_version_is_nonempty(client: TestClient) -> None:
    """version MUST be a non-empty string (imported from package __version__)."""
    body = client.get("/health").json()
    assert isinstance(body.get("version"), str) and body.get("version"), (
        f"'version' must be a non-empty string, got {body.get('version')!r}"
    )
