"""Region payload caps tests (Hot-Fix H2).

The 100 kb span cap alone did not bound payload size because the
`clinvar_variants` and `genes` lists were uncapped. A reviewer reported
`get_region` returning 3 MB on an 81 kb BRCA1 window. These tests pin the
new per-category caps + compact row projection + `truncated_payload`
metadata.
"""

from __future__ import annotations

from typing import Any

import pytest


class _FatRegionService:
    """Stub FrequencyService that returns oversized region payloads."""

    def __init__(self) -> None:
        self.last_region: tuple[str, int, int, str] | None = None

    async def get_region(self, chrom: str, start: int, stop: int, dataset: str) -> dict[str, Any]:
        self.last_region = (chrom, start, stop, dataset)
        return {
            "region": {
                "chrom": chrom,
                "start": start,
                "stop": stop,
                "reference_genome": "GRCh38",
                "clinvar_variants": [
                    {
                        "variant_id": f"{chrom}-{start + i}-A-G",
                        "clinical_significance": "Pathogenic",
                        "review_status": "criteria provided, single submitter",
                        "gold_stars": 1,
                        "major_consequence": "missense_variant",
                        "submissions": [{"clinical_significance": "Pathogenic"}] * 5,
                        "raw_extra": "x" * 200,
                    }
                    for i in range(250)
                ],
                "genes": [
                    {
                        "gene_id": f"ENSG{i:011d}",
                        "symbol": f"GENE{i}",
                        "chrom": chrom,
                        "start": start + i,
                        "stop": start + i + 1000,
                        "transcripts": [{"transcript_id": f"ENST{i:011d}"}] * 10,
                    }
                    for i in range(75)
                ],
            }
        }


@pytest.mark.asyncio
async def test_get_region_caps_clinvar_variants_default() -> None:
    """With defaults the lists are capped at 100/50 and truncated_payload is emitted."""

    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _FatRegionService()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    result = await mcp.call_tool(
        "get_region",
        {"region": "17-43044000-43125000", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    assert len(payload["clinvar_variants"]) == 100
    assert len(payload["genes"]) == 50
    trunc = payload["truncated_payload"]
    assert trunc["kind"] == "region_payload"
    assert trunc["dropped"] == {"clinvar_variants": 150, "genes": 25}
    assert "to_disable" in trunc
    assert "max_clinvar_variants" in trunc["to_disable"] or "max_genes" in trunc["to_disable"]
    assert "to_restore" in trunc


@pytest.mark.asyncio
async def test_get_region_respects_max_clinvar_variants() -> None:
    """Explicit max_clinvar_variants overrides the default."""

    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _FatRegionService()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    result = await mcp.call_tool(
        "get_region",
        {
            "region": "17-43044000-43125000",
            "dataset": "gnomad_r4",
            "max_clinvar_variants": 10,
        },
    )
    payload = result.structured_content or {}

    assert len(payload["clinvar_variants"]) == 10
    assert payload["truncated_payload"]["dropped"]["clinvar_variants"] == 240


@pytest.mark.asyncio
async def test_get_region_respects_max_genes() -> None:
    """Explicit max_genes overrides the default."""

    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _FatRegionService()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    result = await mcp.call_tool(
        "get_region",
        {
            "region": "17-43044000-43125000",
            "dataset": "gnomad_r4",
            "max_genes": 5,
        },
    )
    payload = result.structured_content or {}

    assert len(payload["genes"]) == 5
    assert payload["truncated_payload"]["dropped"]["genes"] == 70


@pytest.mark.asyncio
async def test_get_region_skips_caps_when_lists_excluded() -> None:
    """include_clinvar=False / include_genes=False removes lists and skips truncated_payload."""

    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _FatRegionService()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    result = await mcp.call_tool(
        "get_region",
        {
            "region": "17-43044000-43125000",
            "dataset": "gnomad_r4",
            "include_clinvar": False,
            "include_genes": False,
        },
    )
    payload = result.structured_content or {}

    assert "clinvar_variants" not in payload
    assert "genes" not in payload
    assert "truncated_payload" not in payload


@pytest.mark.asyncio
async def test_get_region_compacts_clinvar_rows() -> None:
    """Compact mode projects clinvar rows to a small key set, dropping bulk fields."""

    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _FatRegionService()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    result = await mcp.call_tool(
        "get_region",
        {"region": "17-43044000-43125000", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    row = payload["clinvar_variants"][0]
    # Kept keys
    assert "variant_id" in row
    assert "clinical_significance" in row
    assert "review_status" in row
    assert "gold_stars" in row
    assert "major_consequence" in row
    # Bulk keys dropped under compact_rows=True
    assert "submissions" not in row
    assert "raw_extra" not in row


@pytest.mark.asyncio
async def test_get_region_compacts_gene_rows() -> None:
    """Compact mode drops heavy arrays like transcripts from gene rows."""

    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _FatRegionService()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    result = await mcp.call_tool(
        "get_region",
        {"region": "17-43044000-43125000", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    gene = payload["genes"][0]
    assert "gene_id" in gene
    assert "symbol" in gene
    assert "chrom" in gene
    assert "start" in gene
    assert "stop" in gene
    # Bulk array dropped
    assert "transcripts" not in gene


@pytest.mark.asyncio
async def test_get_region_full_rows_when_compact_disabled() -> None:
    """compact_rows=False preserves all upstream fields."""

    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _FatRegionService()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    result = await mcp.call_tool(
        "get_region",
        {
            "region": "17-43044000-43125000",
            "dataset": "gnomad_r4",
            "compact_rows": False,
            "max_clinvar_variants": 5,
            "max_genes": 3,
        },
    )
    payload = result.structured_content or {}

    row = payload["clinvar_variants"][0]
    # Bulk keys preserved when compact_rows=False
    assert "submissions" in row
    assert "raw_extra" in row
    gene = payload["genes"][0]
    assert "transcripts" in gene


@pytest.mark.asyncio
async def test_get_region_combines_span_cap_and_payload_cap() -> None:
    """A huge span AND large lists must emit BOTH truncated (span) and truncated_payload."""

    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _FatRegionService()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    # 500kb span exceeds the 100kb cap.
    result = await mcp.call_tool(
        "get_region",
        {"region": "17-43000000-43500000", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    # Span cap fires on the existing top-level `truncated` block.
    assert payload["truncated"]["kind"] == "region_span"
    # List cap fires on the new top-level `truncated_payload` block.
    assert payload["truncated_payload"]["kind"] == "region_payload"
