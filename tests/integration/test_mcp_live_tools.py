"""Live MCP tool tests against the gnomAD upstream. Gated by the `integration` marker."""

from __future__ import annotations

import pytest

from gnomad_link.api.client import UnifiedGnomadClient
from gnomad_link.mcp.facade import create_gnomad_mcp
from gnomad_link.services.frequency_service import FrequencyService

pytestmark = pytest.mark.integration


@pytest.fixture
def mcp_with_live_service():
    service = FrequencyService(client=UnifiedGnomadClient())
    return create_gnomad_mcp(service_factory=lambda: service)


@pytest.mark.asyncio
async def test_get_variant_frequencies_live(mcp_with_live_service) -> None:
    result = await mcp_with_live_service.call_tool(
        "get_variant_frequencies",
        {"variant_id": "1-55051215-G-GA", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}
    assert payload["variant_id"] == "1-55051215-G-GA"
    assert payload["exome"] is not None
    afr = next(p for p in payload["exome"]["populations"] if p["id"] == "afr")
    assert afr["af"] > 0.01


@pytest.mark.asyncio
async def test_get_gene_details_live(mcp_with_live_service) -> None:
    result = await mcp_with_live_service.call_tool("get_gene_details", {"gene_symbol": "PCSK9"})
    payload = result.structured_content or {}
    assert payload["symbol"] == "PCSK9"
    assert payload["gnomad_constraint"]["pLI"] is not None


@pytest.mark.asyncio
async def test_resolve_variant_id_returns_ids_only(mcp_with_live_service) -> None:
    result = await mcp_with_live_service.call_tool("resolve_variant_id", {"query": "rs11591147"})
    payload = result.structured_content or {}
    assert payload["returned"] >= 1
    for r in payload["results"]:
        assert "variant_id" in r


@pytest.mark.asyncio
async def test_get_region_caps_span(mcp_with_live_service) -> None:
    result = await mcp_with_live_service.call_tool("get_region", {"region": "1-55000000-56000000"})
    payload = result.structured_content or {}
    assert payload.get("truncated", {}).get("kind") == "region_span"


@pytest.mark.asyncio
async def test_get_gene_variants_caps_at_limit(mcp_with_live_service) -> None:
    result = await mcp_with_live_service.call_tool(
        "get_gene_variants",
        {"gene_id": "ENSG00000155657", "limit": 50},  # TTN
    )
    payload = result.structured_content or {}
    assert payload["returned"] == 50
    assert payload.get("truncated", {}).get("kind") == "gene_variants"
