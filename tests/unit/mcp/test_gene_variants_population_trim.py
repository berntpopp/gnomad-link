"""L-4 follow-through: get_gene_variants must trim per-variant populations.

Each variant row carries its own exome/genome population breakdown. At the
default limit of 100 that is up to 100 x ~28 rows, almost all ac==0 — the
list-endpoint analogue of the get_variant_details firehose. These tests pin
per-variant trimming, the populations-off scan mode, and a single payload-level
projection note (not 100 per-variant truncated blocks).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

import mcp.types
from gnomad_link.mcp.shaping import shape_gene_variants


def _raw() -> list[dict[str, Any]]:
    return [
        {
            "variant_id": "12-1-A-T",
            "pos": 1,
            "ref": "A",
            "alt": "T",
            "consequence": "missense_variant",
            "af": 0.0005,
            "ac": 5,
            "exome": {
                "ac": 5,
                "an": 10_000,
                "af": 0.0005,
                "filters": [],
                "populations": [
                    {"id": "afr", "ac": 5, "an": 4_000, "homozygote_count": 0},
                    {"id": "nfe", "ac": 0, "an": 6_000, "homozygote_count": 0},
                    {"id": "nfe_XX", "ac": 0, "an": 3_000, "homozygote_count": 0},
                    {"id": "hgdp:han", "ac": 0, "an": 66, "homozygote_count": 0},
                ],
            },
            "genome": None,
        }
    ]


def test_default_trims_each_variant_populations() -> None:
    out = shape_gene_variants(_raw(), limit=100, consequence=None, max_af=None, min_ac=None)
    pops = {p["id"] for p in out["variants"][0]["exome"]["populations"]}
    assert pops == {"afr"}


def test_no_per_variant_truncated_block() -> None:
    out = shape_gene_variants(_raw(), limit=100, consequence=None, max_af=None, min_ac=None)
    # Per-variant sources stay clean; the projection is reported once at payload level.
    assert "truncated" not in out["variants"][0]["exome"]
    assert out["population_projection"]["filter"]["exclude_zero_populations"] is True
    assert "to_restore" in out["population_projection"]


def test_include_populations_false_drops_arrays_but_keeps_counts() -> None:
    out = shape_gene_variants(
        _raw(),
        limit=100,
        consequence=None,
        max_af=None,
        min_ac=None,
        include_populations=False,
    )
    exome = out["variants"][0]["exome"]
    assert "populations" not in exome
    assert exome["ac"] == 5 and exome["an"] == 10_000


def test_exclude_zero_false_keeps_zero_base_rows() -> None:
    out = shape_gene_variants(
        _raw(),
        limit=100,
        consequence=None,
        max_af=None,
        min_ac=None,
        exclude_zero_populations=False,
    )
    pops = {p["id"] for p in out["variants"][0]["exome"]["populations"]}
    assert {"afr", "nfe"} <= pops  # nfe is a zero-AC base row, now retained


def test_row_filters_still_apply_with_population_trim() -> None:
    out = shape_gene_variants(
        _raw(), limit=100, consequence="synonymous_variant", max_af=None, min_ac=None
    )
    # The only row is missense; the consequence filter drops it.
    assert out["returned"] == 0
    assert out["truncated"]["dropped"]["by_consequence"] == 1


# --- Tool-level wiring through the real MCP SDK handler. ---


async def _invoke(mcp_instance: Any, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
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


class _GeneVariantsStub:
    async def get_gene_variants(self, gene_id: str, dataset: str) -> list[dict[str, Any]]:
        return _raw()


@pytest.mark.asyncio
async def test_tool_trims_and_passes_output_validation() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=lambda: _GeneVariantsStub())
    payload = await _invoke(mcp, "get_gene_variants", {"gene_id": "ENSG00000273079"})
    assert payload.get("error_code") is None, payload
    assert {p["id"] for p in payload["variants"][0]["exome"]["populations"]} == {"afr"}
    assert payload["population_projection"]["filter"]["exclude_zero_populations"] is True


@pytest.mark.asyncio
async def test_tool_include_populations_false_flows_through() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=lambda: _GeneVariantsStub())
    payload = await _invoke(
        mcp, "get_gene_variants", {"gene_id": "ENSG00000273079", "include_populations": False}
    )
    assert "populations" not in payload["variants"][0]["exome"]
