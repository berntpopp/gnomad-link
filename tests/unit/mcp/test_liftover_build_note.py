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
    # Forward conversion exposes the GRCh38 coordinate directly + labels direction.
    assert payload["query_type"] == "forward"
    assert payload["target_reference_genome"] == "GRCh38"
    assert payload["results"][0]["target_variant_id"] == "1-54585542-G-GA"


@pytest.mark.asyncio
async def test_reverse_direction_exposes_grch37_target() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    # gnomAD returns the same record regardless of which key the id bound to;
    # for a GRCh38 source the answer is the GRCh37 `source` entry.
    mapping = [
        {
            "source": {"variant_id": "1-55516888-G-GA", "reference_genome": "GRCh37"},
            "liftover": {"variant_id": "1-55051215-G-GA", "reference_genome": "GRCh38"},
            "datasets": ["gnomad_r4"],
        }
    ]
    mcp = create_gnomad_mcp(service_factory=lambda: _LiftoverStub(results=mapping))
    result = await mcp.call_tool(
        "liftover_variant",
        {"source_variant_id": "1-55051215-G-GA", "source_genome": "GRCh38"},
    )
    payload = result.structured_content or {}

    assert payload["query_type"] == "reverse"
    assert payload["target_reference_genome"] == "GRCh37"
    assert payload["results"][0]["target_variant_id"] == "1-55516888-G-GA"


@pytest.mark.asyncio
async def test_client_get_liftover_picks_direction_argument() -> None:
    """GRCh37 source binds source_variant_id; GRCh38 source binds liftover_variant_id."""
    from unittest.mock import AsyncMock, patch

    from gnomad_link.api.client import UnifiedGnomadClient

    client = UnifiedGnomadClient()
    with patch.object(client, "execute_query", new=AsyncMock(return_value={"liftover": []})) as eq:
        await client.get_liftover("1-1-A-G", "GRCh37")
        fwd_vars = eq.call_args.args[1]
        assert fwd_vars.get("source_variant_id") == "1-1-A-G"
        assert "liftover_variant_id" not in fwd_vars

        await client.get_liftover("1-2-A-G", "GRCh38")
        rev_vars = eq.call_args.args[1]
        assert rev_vars.get("liftover_variant_id") == "1-2-A-G"
        assert "source_variant_id" not in rev_vars
    await client.close()
