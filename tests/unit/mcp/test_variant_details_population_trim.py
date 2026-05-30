"""L-4 follow-through: get_variant_details must trim the population firehose.

The sibling tool get_variant_frequencies trims subcohort / sex-split / zero-AC
rows by default, but shape_variant_details_compact passed exome/genome through
raw. A common variant (e.g. F508del) therefore dumped 200+ mostly-zero HGDP/1kg
rows under the advertised "compact ~3kB" — the largest residual token sink in
the facade. These tests pin the trimming, the toggles, and the QC-`filters`
preservation, mirroring test_frequency_shaping.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

import mcp.types
from gnomad_link.mcp.shaping import shape_variant_details_compact


def _raw_variant() -> dict[str, Any]:
    return {
        "variant_id": "7-117559590-ATCT-A",
        "pos": 117559590,
        "ref": "ATCT",
        "alt": "A",
        "major_consequence": "inframe_deletion",
        "in_silico_predictors": [{"id": "cadd", "value": "19.2", "flags": []}],
        "transcript_consequences": [{"gene_symbol": "CFTR", "canonical": True}],
        "exome": {
            "ac": 220,
            "an": 300_000,
            "homozygote_count": 2,
            "hemizygote_count": 0,
            "filters": ["AC0"],
            "populations": [
                {"id": "afr", "ac": 143, "an": 8_000, "homozygote_count": 2},
                {"id": "nfe", "ac": 7, "an": 150_000, "homozygote_count": 0},
                {"id": "asj", "ac": 0, "an": 1_000, "homozygote_count": 0},
                {"id": "nfe_XX", "ac": 4, "an": 75_000, "homozygote_count": 0},
                {"id": "hgdp:french", "ac": 2, "an": 54, "homozygote_count": 0},
            ],
        },
        "genome": None,
    }


def test_compact_trims_subcohort_sex_split_and_zero_ac() -> None:
    out = shape_variant_details_compact(_raw_variant())
    pops = {p["id"] for p in out["exome"]["populations"]}
    assert pops == {"afr", "nfe"}
    assert out["exome"]["populations"][0]["af"] is not None


def test_compact_emits_populations_truncated_block() -> None:
    out = shape_variant_details_compact(_raw_variant())
    trunc = out["exome"]["truncated"]
    assert trunc["kind"] == "populations"
    assert trunc["dropped"] == {
        "zero_ac": 1,
        "subcohorts": 1,
        "sex_split": 1,
        "not_selected": 0,
    }
    assert "to_restore" in trunc


def test_compact_preserves_source_filters_and_counts() -> None:
    out = shape_variant_details_compact(_raw_variant())
    assert out["exome"]["filters"] == ["AC0"]
    assert out["exome"]["ac"] == 220
    assert out["exome"]["hemizygote_count"] == 0


def test_compact_none_genome_passes_through() -> None:
    out = shape_variant_details_compact(_raw_variant())
    assert out["genome"] is None


def test_include_subcohorts_keeps_prefixed_rows() -> None:
    out = shape_variant_details_compact(_raw_variant(), include_subcohorts=True)
    pops = {p["id"] for p in out["exome"]["populations"]}
    assert "hgdp:french" in pops


def test_populations_select_restricts_rows() -> None:
    out = shape_variant_details_compact(_raw_variant(), populations=["afr"])
    assert [p["id"] for p in out["exome"]["populations"]] == ["afr"]


def test_transcript_cap_still_fires_alongside_population_trim() -> None:
    raw = _raw_variant()
    raw["transcript_consequences"] = [{"gene_symbol": "CFTR"} for _ in range(15)]
    out = shape_variant_details_compact(raw, max_transcripts=10)
    assert len(out["transcript_consequences"]) == 10
    # The transcript truncation block must not be clobbered by population trimming.
    assert out["truncated"]["kind"] == "transcript_consequences"
    # ...and the per-source population truncation lives under exome, not top-level.
    assert out["exome"]["truncated"]["kind"] == "populations"


# --- Tool-level wiring: params reach the shaper and the trimmed shape survives
# output-schema validation through the real MCP SDK handler. ---


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


class _Stub:
    async def get_variant(self, variant_id: str, dataset: str) -> dict[str, Any]:
        return {"variant": _raw_variant()}


@pytest.mark.asyncio
async def test_tool_default_trims_and_passes_output_validation() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=lambda: _Stub())
    payload = await _invoke(
        mcp, "get_variant_details", {"variant_id": "7-117559590-ATCT-A", "dataset": "gnomad_r4"}
    )
    assert payload.get("error_code") is None, payload
    assert {p["id"] for p in payload["exome"]["populations"]} == {"afr", "nfe"}
    assert payload["exome"]["truncated"]["kind"] == "populations"


@pytest.mark.asyncio
async def test_tool_include_subcohorts_flag_flows_through() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=lambda: _Stub())
    payload = await _invoke(
        mcp,
        "get_variant_details",
        {"variant_id": "7-117559590-ATCT-A", "include_subcohorts": True},
    )
    assert "hgdp:french" in {p["id"] for p in payload["exome"]["populations"]}
