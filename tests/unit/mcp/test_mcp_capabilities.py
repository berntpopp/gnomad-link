from __future__ import annotations

import pytest


def test_capabilities_payload_shape() -> None:
    from gnomad_link.mcp.resources import get_capabilities_resource

    payload = get_capabilities_resource()

    assert payload["server"] == "gnomad-link"
    assert payload["research_use_only"] is True
    assert "gnomad_r4" in payload["datasets"]
    assert payload["datasets"]["gnomad_r4"]["default"] is True
    assert "afr" in payload["population_codes"]
    assert "_XX" in payload["population_suffixes"]
    assert "variant_id -> get_variant_frequencies" in payload["recommended_workflows"]
    assert "resolve_variant_id" in payload["tools"]
    assert "get_variant_frequencies" in payload["tools"]


def test_capabilities_payload_includes_version_and_protocol() -> None:
    from gnomad_link.mcp.resources import get_capabilities_resource

    payload = get_capabilities_resource()

    assert "server_version" in payload
    assert "mcp_protocol_version" in payload


@pytest.mark.asyncio
async def test_get_server_capabilities_tool_returns_capabilities(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    result = await mcp.call_tool("get_server_capabilities", {})

    payload = result.structured_content or {}
    assert payload["server"] == "gnomad-link"
    assert isinstance(payload["tools"], list)
