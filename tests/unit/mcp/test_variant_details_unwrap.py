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

import json
from typing import Any

import pytest

import mcp.types


async def _invoke(mcp_instance: Any, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Route through the SDK lowlevel handler so output-schema validation runs."""
    handler = mcp_instance._mcp_server.request_handlers[mcp.types.CallToolRequest]
    request = mcp.types.CallToolRequest(
        method="tools/call",
        params=mcp.types.CallToolRequestParams(name=tool, arguments=arguments),
    )
    result = await handler(request)
    call_result = result.root if hasattr(result, "root") else result
    assert isinstance(call_result, mcp.types.CallToolResult)
    if call_result.structuredContent is not None:
        return dict(call_result.structuredContent)
    if call_result.content:
        text = getattr(call_result.content[0], "text", None)
        if isinstance(text, str):
            return json.loads(text)
    return {}


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
    # gnomAD returns predictors as a LIST of {id, value, flags} rows.
    "in_silico_predictors": [
        {"id": "cadd", "value": "19.2", "flags": []},
        {"id": "spliceai_ds_max", "value": "0.00", "flags": []},
    ],
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
    payload = await _invoke(
        mcp,
        "get_variant_details",
        {"variant_id": "7-117559590-ATCT-A", "dataset": "gnomad_r4"},
    )

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
    # Route through the lowlevel handler so output-schema validation actually runs.
    payload = await _invoke(
        mcp,
        "get_variant_details",
        {
            "variant_id": "7-117559590-ATCT-A",
            "dataset": "gnomad_r4",
            "response_mode": "full",
        },
    )

    assert payload.get("variant_id") == "7-117559590-ATCT-A", payload
    # Full mode is unwrapped too — never the {"variant": {...}} wrapper.
    assert "variant" not in payload or isinstance(payload.get("variant"), str)
    # in_silico_predictors is a list of rows (gnomAD shape), and the list-valued
    # payload must survive output-schema validation (regression: the model used to
    # type this as a dict, so the real list tripped output_validation_failed).
    assert payload.get("error_code") != "output_validation_failed", payload
    assert isinstance(payload.get("in_silico_predictors"), list)
    assert payload["in_silico_predictors"][0]["id"] == "cadd"


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
