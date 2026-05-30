"""Input-schema tightening (#11): malformed ids and invalid datasets are rejected
at the MCP argument boundary with a validation_failed envelope, instead of being
forwarded upstream to 404.

Validation runs in the FastMCP argument wrapper before the tool body, so a
trivial service factory is sufficient.
"""

from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.mcp.facade import create_gnomad_mcp
from gnomad_link.mcp.patterns import GENE_ID_PATTERN, GENE_SYMBOL_PATTERN

_SV_REGION_PATTERN = r"^(chr)?([1-9]|1[0-9]|2[0-2]|X|Y)-\d+-\d+$"


def _noop_service_factory() -> Any:
    return object()


def _structured(result: Any) -> dict[str, Any]:
    return result.structured_content or {}


def _is_validation_failed(payload: dict[str, Any]) -> bool:
    return payload.get("success") is False and payload.get("error_code") == "validation_failed"


@pytest.mark.asyncio
async def test_clinvar_rejects_non_coordinate_id() -> None:
    mcp = create_gnomad_mcp(service_factory=_noop_service_factory)
    result = await mcp.call_tool(
        "get_clinvar_variant_details",
        {"variant_id": "rs113993960", "reference_genome": "GRCh38"},
    )
    assert _is_validation_failed(_structured(result))


@pytest.mark.asyncio
async def test_transcript_rejects_malformed_id() -> None:
    mcp = create_gnomad_mcp(service_factory=_noop_service_factory)
    result = await mcp.call_tool(
        "get_transcript_details",
        {"transcript_id": "NOT-A-TRANSCRIPT"},
    )
    assert _is_validation_failed(_structured(result))


@pytest.mark.asyncio
async def test_compare_rejects_invalid_dataset_in_list() -> None:
    mcp = create_gnomad_mcp(service_factory=_noop_service_factory)
    result = await mcp.call_tool(
        "compare_variant_across_datasets",
        {"variant_id": "1-55039974-G-T", "datasets": ["gnomad_r4", "not_a_dataset"]},
    )
    assert _is_validation_failed(_structured(result))


def _string_pattern(schema: dict[str, Any]) -> str | None:
    if schema.get("type") == "string":
        pattern = schema.get("pattern")
        return pattern if isinstance(pattern, str) else None
    for option in schema.get("anyOf", []):
        if option.get("type") == "string":
            pattern = option.get("pattern")
            return pattern if isinstance(pattern, str) else None
    return None


@pytest.mark.asyncio
async def test_gene_tools_advertise_uniform_id_and_symbol_patterns() -> None:
    mcp = create_gnomad_mcp(service_factory=_noop_service_factory)
    tools = {tool.name: tool for tool in await mcp.list_tools()}

    expected = {
        "get_gene_details": {
            "gene_id": GENE_ID_PATTERN,
            "gene_symbol": GENE_SYMBOL_PATTERN,
        },
        "get_gene_variants": {"gene_id": GENE_ID_PATTERN},
        "get_gene_summary": {
            "gene_id": GENE_ID_PATTERN,
            "gene_symbol": GENE_SYMBOL_PATTERN,
        },
        "search_structural_variants": {
            "gene_id": GENE_ID_PATTERN,
            "gene_symbol": GENE_SYMBOL_PATTERN,
            "region": _SV_REGION_PATTERN,
        },
    }

    for tool_name, properties in expected.items():
        params = tools[tool_name].parameters["properties"]
        for field, pattern in properties.items():
            assert _string_pattern(params[field]) == pattern


@pytest.mark.asyncio
async def test_structural_variant_search_rejects_mitochondrial_region() -> None:
    mcp = create_gnomad_mcp(service_factory=_noop_service_factory)
    result = await mcp.call_tool(
        "search_structural_variants",
        {"region": "MT-1-200", "sv_dataset": "gnomad_sv_r4"},
    )
    assert _is_validation_failed(_structured(result))
