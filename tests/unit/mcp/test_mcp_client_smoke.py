from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from gnomad_link.mcp.facade import create_gnomad_mcp


@pytest.mark.asyncio
async def test_in_process_client_lists_tools_and_reads_capabilities() -> None:
    service = AsyncMock()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    assert {"get_server_capabilities", "get_variant_frequencies", "resolve_variant_id"} <= names

    result = await mcp.call_tool("get_server_capabilities", {})
    payload = result.structured_content or {}
    assert payload["server"] == "gnomad-link"
    assert "datasets" in payload
    assert "recommended_workflows" in payload


@pytest.mark.asyncio
async def test_in_process_client_reads_capabilities_resource() -> None:
    service = AsyncMock()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    contents = await mcp.read_resource("gnomad://capabilities")
    assert contents
