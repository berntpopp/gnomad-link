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
    # The model serializes the constraint field as `pli` (alias `pLI` is input-only).
    assert payload["gnomad_constraint"]["pli"] is not None


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


@pytest.mark.asyncio
async def test_get_variant_details_trims_populations_live(mcp_with_live_service) -> None:
    """L-4: compact get_variant_details must trim the live population firehose.

    F508del carries 200+ HGDP/1kg/sex-split/zero-AC rows upstream; compact mode
    must drop them to base ac>0 rows and emit a per-source populations truncation.
    """
    result = await mcp_with_live_service.call_tool(
        "get_variant_details",
        {"variant_id": "7-117559590-ATCT-A", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}
    assert payload.get("error_code") is None, payload
    exome = payload["exome"]
    ids = [p["id"] for p in exome["populations"]]
    # No subcohort, sex-split, or zero-AC rows survive the compact default.
    assert not any(":" in i or i.endswith(("_XX", "_XY")) or i in {"XX", "XY"} for i in ids)
    assert all(p["ac"] > 0 for p in exome["populations"])
    assert exome["truncated"]["kind"] == "populations"
    # Exome always carries _XX/_XY sex-split rows; subcohorts live in the genome.
    assert exome["truncated"]["dropped"]["sex_split"] > 0
    genome_dropped = payload["genome"]["truncated"]["dropped"]
    assert genome_dropped["subcohorts"] > 0  # hgdp:/1kg: rows trimmed from genome


@pytest.mark.asyncio
async def test_get_variant_details_full_keeps_all_populations_live(mcp_with_live_service) -> None:
    """response_mode='full' is the documented escape hatch — nothing trimmed."""
    result = await mcp_with_live_service.call_tool(
        "get_variant_details",
        {"variant_id": "7-117559590-ATCT-A", "dataset": "gnomad_r4", "response_mode": "full"},
    )
    payload = result.structured_content or {}
    ids = [p["id"] for p in payload["genome"]["populations"]]
    assert any(":" in i for i in ids)  # subcohorts present in full mode


@pytest.mark.asyncio
async def test_get_gene_variants_population_projection_live(mcp_with_live_service) -> None:
    """L-4: each variant's populations are trimmed; include_populations=False drops them."""
    trimmed = await mcp_with_live_service.call_tool(
        "get_gene_variants",
        {"gene_id": "ENSG00000273079", "limit": 20},  # GRIN2B
    )
    tp = trimmed.structured_content or {}
    assert tp.get("population_projection", {}).get("filter", {}).get("exclude_zero_populations")
    for v in tp["variants"]:
        for src in ("exome", "genome"):
            if isinstance(v.get(src), dict) and "populations" in v[src]:
                assert all(p["ac"] > 0 for p in v[src]["populations"])

    lean = await mcp_with_live_service.call_tool(
        "get_gene_variants",
        {"gene_id": "ENSG00000273079", "limit": 20, "include_populations": False},
    )
    lp = lean.structured_content or {}
    for v in lp["variants"]:
        for src in ("exome", "genome"):
            if isinstance(v.get(src), dict):
                assert "populations" not in v[src]


@pytest.mark.asyncio
async def test_compare_finds_hfe_c282y_in_r2_1_live(mcp_with_live_service) -> None:
    """Phase-1 regression (live): HFE C282Y must resolve in gnomad_r2_1 via auto-liftover.

    GRCh38 6-26092913-G-A lifts to GRCh37 6-26093141-G-A; the compare tool must
    report the r2_1 leg present (was a false present:false before the fix).
    """
    result = await mcp_with_live_service.call_tool(
        "compare_variant_across_datasets",
        {
            "variant_id": "6-26092913-G-A",
            "datasets": ["gnomad_r4", "gnomad_r2_1"],
            "auto_liftover": True,
        },
    )
    payload = result.structured_content or {}
    r2 = payload["datasets"]["gnomad_r2_1"]
    assert r2["present"] is True
    assert r2.get("lifted_variant_id") == "6-26093141-G-A"
