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


def _structured(result: Any) -> dict[str, Any]:
    return result.structured_content or {}


def _is_validation_failed(payload: dict[str, Any]) -> bool:
    return payload.get("success") is False and payload.get("error_code") == "validation_failed"


@pytest.mark.asyncio
async def test_clinvar_rejects_non_coordinate_id() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: object())
    result = await mcp.call_tool(
        "get_clinvar_variant_details",
        {"variant_id": "rs113993960", "reference_genome": "GRCh38"},
    )
    assert _is_validation_failed(_structured(result))


@pytest.mark.asyncio
async def test_transcript_rejects_malformed_id() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: object())
    result = await mcp.call_tool(
        "get_transcript_details",
        {"transcript_id": "NOT-A-TRANSCRIPT"},
    )
    assert _is_validation_failed(_structured(result))


@pytest.mark.asyncio
async def test_compare_rejects_invalid_dataset_in_list() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: object())
    result = await mcp.call_tool(
        "compare_variant_across_datasets",
        {"variant_id": "1-55039974-G-T", "datasets": ["gnomad_r4", "not_a_dataset"]},
    )
    assert _is_validation_failed(_structured(result))
