"""L-1: liftover_variant must explain an empty mapping instead of bare results:[]."""

from __future__ import annotations

from typing import Any

import pytest


class _LiftoverStub:
    def __init__(self, *, results: list[dict[str, Any]]) -> None:
        self._results = results

    async def liftover_variant(
        self, source_variant_id: str, reference_genome: str
    ) -> list[dict[str, Any]]:
        return self._results


@pytest.mark.asyncio
async def test_empty_liftover_emits_build_note() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=lambda: _LiftoverStub(results=[]))
    result = await mcp.call_tool(
        "liftover_variant",
        {"source_variant_id": "1-55051215-G-GA", "source_genome": "GRCh37"},
    )
    payload = result.structured_content or {}

    assert payload.get("results") == []
    assert "build_note" in payload, payload
    assert "GRCh38" in payload["build_note"]
    assert "resolve_variant_id" in payload["build_note"]


@pytest.mark.asyncio
async def test_non_empty_liftover_has_no_build_note() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mapping = [
        {
            "source": {"variant_id": "1-55051215-G-GA", "reference_genome": "GRCh37"},
            "liftover": {"variant_id": "1-54585542-G-GA", "reference_genome": "GRCh38"},
            "datasets": ["gnomad_r4"],
        }
    ]
    mcp = create_gnomad_mcp(service_factory=lambda: _LiftoverStub(results=mapping))
    result = await mcp.call_tool(
        "liftover_variant",
        {"source_variant_id": "1-55051215-G-GA", "source_genome": "GRCh37"},
    )
    payload = result.structured_content or {}

    assert payload.get("results")
    assert "build_note" not in payload
