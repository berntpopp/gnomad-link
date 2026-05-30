"""H-1 regression: get_variant_details must not silently return a bare _meta.

The bug: ``service.get_variant`` returns the GraphQL wrapper ``{"variant": {...}}``,
but the tool fed that straight into ``shape_variant_details_compact`` whose keep-set
keys live one level deeper. The compact projection therefore matched nothing and the
tool returned only the injected ``_meta`` block — a silent-empty success, the worst
failure mode for an LLM (it confidently reports "no annotation found").

These tests pin: (1) a known variant yields a non-empty variant block in compact and
full modes, and (2) a missing variant yields an explicit not_found envelope rather
than an empty payload.
"""

from __future__ import annotations

from typing import Any

import pytest

_RAW_VARIANT = {
    "variant_id": "7-117559590-ATCT-A",
    "reference_genome": "GRCh38",
    "pos": 117559590,
    "ref": "ATCT",
    "alt": "A",
    "rsids": ["rs113993960"],
    "major_consequence": "inframe_deletion",
    "transcript_consequences": [
        {
            "transcript_id": "ENST00000003084",
            "gene_symbol": "CFTR",
            "biotype": "protein_coding",
            "canonical": True,
            "major_consequence": "inframe_deletion",
        }
    ],
    "in_silico_predictors": {"cadd": 22.1},
    "clinvar": {"clinical_significance": "Pathogenic"},
    "exome": {"ac": 1000, "an": 1200000, "populations": []},
    "genome": None,
}


class _VariantDetailsStub:
    """Stub whose get_variant returns the wrapped GraphQL payload (as the client does)."""

    def __init__(self, *, found: bool = True) -> None:
        self._found = found

    async def get_variant(self, variant_id: str, dataset: str) -> dict[str, Any]:
        if not self._found:
            from gnomad_link.api.base_client import VariantNotFoundError

            raise VariantNotFoundError(f"Variant {variant_id} not found in {dataset}")
        return {"variant": dict(_RAW_VARIANT)}


@pytest.mark.asyncio
async def test_get_variant_details_compact_returns_variant_block() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=lambda: _VariantDetailsStub())
    result = await mcp.call_tool(
        "get_variant_details",
        {"variant_id": "7-117559590-ATCT-A", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    assert payload.get("error_code") is None, payload
    # The whole point of H-1: the variant block is present, not a bare _meta.
    assert payload.get("variant_id") == "7-117559590-ATCT-A", payload
    assert payload.get("transcript_consequences"), payload
    assert payload.get("clinvar") == {"clinical_significance": "Pathogenic"}
    # Sanity: more than just the injected _meta survived.
    assert set(payload) - {"_meta"}


@pytest.mark.asyncio
async def test_get_variant_details_full_returns_variant_block() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=lambda: _VariantDetailsStub())
    result = await mcp.call_tool(
        "get_variant_details",
        {
            "variant_id": "7-117559590-ATCT-A",
            "dataset": "gnomad_r4",
            "response_mode": "full",
        },
    )
    payload = result.structured_content or {}

    assert payload.get("variant_id") == "7-117559590-ATCT-A", payload
    # Full mode is unwrapped too — never the {"variant": {...}} wrapper.
    assert "variant" not in payload or isinstance(payload.get("variant"), str)
    assert payload.get("in_silico_predictors") == {"cadd": 22.1}


@pytest.mark.asyncio
async def test_get_variant_details_missing_returns_not_found() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=lambda: _VariantDetailsStub(found=False))
    result = await mcp.call_tool(
        "get_variant_details",
        {"variant_id": "7-117559590-ATCT-A", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    assert payload.get("success") is False, payload
    assert payload.get("error_code") == "not_found", payload
