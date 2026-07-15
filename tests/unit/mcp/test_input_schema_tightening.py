"""Input-schema tightening (#11): malformed ids and invalid datasets are rejected
at the MCP argument boundary with an invalid_input envelope, instead of being
forwarded upstream to 404.

Validation runs in the FastMCP argument wrapper before the tool body, so a
trivial service factory is sufficient.
"""

from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.mcp.facade import create_gnomad_mcp
from gnomad_link.mcp.patterns import GENE_ID_PATTERN


def _noop_service_factory() -> Any:
    return object()


def _structured(result: Any) -> dict[str, Any]:
    return result.structured_content or {}


def _is_invalid_input(payload: dict[str, Any]) -> bool:
    return payload.get("success") is False and payload.get("error_code") == "invalid_input"


@pytest.mark.asyncio
async def test_clinvar_rejects_non_coordinate_id() -> None:
    mcp = create_gnomad_mcp(service_factory=_noop_service_factory)
    result = await mcp.call_tool(
        "get_clinvar_variant_details",
        {"variant_id": "rs113993960", "reference_genome": "GRCh38"},
    )
    assert _is_invalid_input(_structured(result))


@pytest.mark.asyncio
async def test_transcript_rejects_malformed_id() -> None:
    mcp = create_gnomad_mcp(service_factory=_noop_service_factory)
    result = await mcp.call_tool(
        "get_transcript_details",
        {"transcript_id": "NOT-A-TRANSCRIPT"},
    )
    assert _is_invalid_input(_structured(result))


@pytest.mark.asyncio
async def test_compare_rejects_invalid_dataset_in_list() -> None:
    mcp = create_gnomad_mcp(service_factory=_noop_service_factory)
    result = await mcp.call_tool(
        "compare_variant_across_datasets",
        {"variant_id": "1-55039974-G-T", "datasets": ["gnomad_r4", "not_a_dataset"]},
    )
    assert _is_invalid_input(_structured(result))


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
async def test_collapsed_gene_tools_expose_single_required_identifier() -> None:
    """The gene/coverage/SV-search tools collapse their one-of identifiers to a
    single REQUIRED param (gene / target) so a valid call is constructible from
    the schema alone (Behaviour-gate control call). get_gene_variants keeps its
    pattern-constrained gene_id (it takes exactly one form)."""
    mcp = create_gnomad_mcp(service_factory=_noop_service_factory)
    tools = {tool.name: tool for tool in await mcp.list_tools()}

    single_required = {
        "get_gene_details": "gene",
        "get_gene_summary": "gene",
        "compute_gene_carrier_frequency": "gene",
        "get_coverage": "target",
        "search_structural_variants": "target",
    }
    for tool_name, param in single_required.items():
        schema = tools[tool_name].parameters
        assert param in schema.get("required", []), (tool_name, schema.get("required"))
        assert param in schema["properties"], (tool_name, param)

    # get_gene_variants still constrains its single-form gene_id.
    gv = tools["get_gene_variants"].parameters["properties"]
    assert _string_pattern(gv["gene_id"]) == GENE_ID_PATTERN
