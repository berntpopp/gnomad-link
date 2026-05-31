"""M-1/L-3: single structural-variant shaping + output-schema null-safety.

- shape_structural_variant trims heavy histograms and the duplicated flat gene
  list (kept under consequences[].genes), with a self-describing truncated block.
- A null-bearing complex/BND payload must pass the SDK output-schema validation
  end-to-end (the M-1 output_validation_failed regression).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

import mcp.types
from gnomad_link.mcp.sv_shaping import shape_structural_variant


def _bnd_payload() -> dict[str, Any]:
    return {
        "variant_id": "CPX_chr1_1",
        "reference_genome": "GRCh38",
        "chrom": "1",
        "type": "CPX",
        "pos": 1000,
        "end": None,  # null upstream for complex/translocation classes
        "af": None,
        "ac": None,
        "an": None,
        "cpx_type": "delINV",
        # gnomAD returns cpx_intervals as interval STRINGS, not objects.
        "cpx_intervals": ["DEL_chr22:10957963-12548894", "INV_chr22:12548894-12600000"],
        "genes": ["GENEA", "GENEB"],
        "consequences": [{"consequence": "lof", "genes": ["GENEA", "GENEB"]}],
        "age_distribution": {"het": {"bin_edges": [0], "bin_freq": [0]}},
        "genotype_quality": {"all": {"bin_edges": [0], "bin_freq": [0]}},
        "populations": [{"id": "afr", "ac": 1, "an": 100}],
    }


def test_compact_drops_histograms_and_duplicated_genes() -> None:
    result = shape_structural_variant(_bnd_payload(), response_mode="compact")

    assert "age_distribution" not in result
    assert "genotype_quality" not in result
    assert "genes" not in result  # flat list dropped; consequences[].genes kept
    assert result["consequences"][0]["genes"] == ["GENEA", "GENEB"]
    trunc = result["truncated"]
    assert trunc["kind"] == "structural_variant"
    assert trunc["to_restore"] == "response_mode='full'"
    assert trunc["dropped"]["genes"] == 2


def test_full_returns_payload_unchanged() -> None:
    payload = _bnd_payload()
    result = shape_structural_variant(payload, response_mode="full")
    assert result is payload
    assert "age_distribution" in result
    assert result["genes"] == ["GENEA", "GENEB"]


def _populated_sv_payload() -> dict[str, Any]:
    """SV payload with a zero-AC row, a sex-split row, and a real hom/hemi row."""
    return {
        "variant_id": "DEL_chr1_42",
        "reference_genome": "GRCh38",
        "chrom": "1",
        "type": "DEL",
        "pos": 1000,
        "end": 2000,
        "af": 0.01,
        "ac": 50,
        "an": 5000,
        "consequences": [{"consequence": "lof", "genes": ["GENEA"]}],
        "genes": ["GENEA"],
        "populations": [
            # Real row with hom/hemi counts that MUST survive intact.
            {
                "id": "nfe",
                "ac": 40,
                "an": 4000,
                "homozygote_count": 3,
                "hemizygote_count": 2,
            },
            # Zero-AC row -> dropped.
            {"id": "afr", "ac": 0, "an": 1000, "homozygote_count": 0},
            # Sex-split row (nonzero AC) -> dropped on sex-split rule.
            {
                "id": "nfe_XX",
                "ac": 20,
                "an": 2000,
                "homozygote_count": 1,
                "hemizygote_count": 0,
            },
        ],
    }


def test_compact_trims_zero_ac_and_sex_split_populations() -> None:
    result = shape_structural_variant(_populated_sv_payload(), response_mode="compact")

    pops = result["populations"]
    ids = {p["id"] for p in pops}
    assert ids == {"nfe"}, pops
    # The surviving real row keeps its hom/hemi counts intact.
    kept = pops[0]
    assert kept["homozygote_count"] == 3
    assert kept["hemizygote_count"] == 2
    assert kept["ac"] == 40 and kept["an"] == 4000
    # truncated reports the two dropped population rows.
    trunc = result["truncated"]
    assert trunc["kind"] == "structural_variant"
    assert trunc["dropped"]["populations"] == 2
    assert trunc["to_restore"] == "response_mode='full'"


def test_full_keeps_all_sv_population_rows() -> None:
    payload = _populated_sv_payload()
    result = shape_structural_variant(payload, response_mode="full")
    assert result is payload
    assert {p["id"] for p in result["populations"]} == {"nfe", "afr", "nfe_XX"}


def test_compact_emits_truncated_when_only_populations_trimmed() -> None:
    """No heavy fields / no flat-gene drop, but a zero-AC pop row trims."""
    payload = {
        "variant_id": "DEL_chr1_7",
        "type": "DEL",
        "populations": [
            {"id": "nfe", "ac": 5, "an": 100},
            {"id": "afr", "ac": 0, "an": 100},
        ],
    }
    result = shape_structural_variant(payload, response_mode="compact")
    assert {p["id"] for p in result["populations"]} == {"nfe"}
    trunc = result["truncated"]
    assert trunc["kind"] == "structural_variant"
    assert trunc["dropped"]["populations"] == 1
    assert trunc["to_restore"] == "response_mode='full'"


def test_compact_leaves_missing_or_empty_populations_alone() -> None:
    payload = {"variant_id": "DEL_chr1_8", "type": "DEL", "populations": []}
    result = shape_structural_variant(payload, response_mode="compact")
    assert result["populations"] == []
    assert "truncated" not in result


def test_flat_genes_kept_when_no_consequences() -> None:
    payload = {"variant_id": "DEL_chr1_9", "genes": ["X"], "consequences": []}
    result = shape_structural_variant(payload, response_mode="compact")
    assert result["genes"] == ["X"]  # not dropped — no grouped view to fall back on


class _SVStub:
    async def get_structural_variant(self, variant_id: str, dataset: str) -> dict[str, Any]:
        return {"structural_variant": _bnd_payload()}


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


def test_compact_population_trim_reduces_serialized_bytes() -> None:
    """Many zero-AC and sex-split rows in compact mode must produce a materially
    smaller JSON serialization than full mode, and the surviving real row keeps
    its hom/hemi counts intact.
    """
    pops = []
    for anc in ["afr", "amr", "asj", "eas", "fin", "nfe", "sas", "mid", "ami"]:
        pops.append({"id": anc, "ac": 0, "an": 1000, "homozygote_count": 0, "hemizygote_count": 0})
        pops.append(
            {"id": f"{anc}_XX", "ac": 5, "an": 500, "homozygote_count": 0, "hemizygote_count": 0}
        )
        pops.append(
            {"id": f"{anc}_XY", "ac": 4, "an": 500, "homozygote_count": 0, "hemizygote_count": 0}
        )
    # Duplicate the "nfe" row with real allele counts; the zero-AC one above is
    # dropped; this one survives (nonzero AC, not sex-split).
    pops.append({"id": "nfe", "ac": 40, "an": 4000, "homozygote_count": 3, "hemizygote_count": 2})
    payload: dict[str, Any] = {
        "variant_id": "DEL_chr1_x",
        "type": "DEL",
        "chrom": "1",
        "pos": 1,
        "end": 100,
        "populations": pops,
    }
    full = shape_structural_variant(dict(payload), response_mode="full")
    compact = shape_structural_variant(dict(payload), response_mode="compact")
    full_bytes = len(json.dumps(full))
    compact_bytes = len(json.dumps(compact))
    assert compact_bytes < full_bytes, (
        f"compact ({compact_bytes} B) must be smaller than full ({full_bytes} B)"
    )
    # The one real autosomal row survives with hom/hemi intact.
    kept = [p for p in compact["populations"] if p["id"] == "nfe" and p.get("ac", 0) > 0]
    assert kept, "expected the real nfe row to survive trimming"
    assert kept[0]["homozygote_count"] == 3
    assert kept[0]["hemizygote_count"] == 2


@pytest.mark.asyncio
async def test_null_bearing_complex_sv_survives_output_validation() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp_instance = create_gnomad_mcp(service_factory=lambda: _SVStub())
    payload = await _invoke(mcp_instance, "get_structural_variant", {"variant_id": "CPX_chr1_1"})

    # The whole M-1 point: null end/af/ac/an must NOT trip output validation.
    assert payload.get("error_code") != "output_validation_failed", payload
    assert payload.get("variant_id") == "CPX_chr1_1", payload
    assert payload.get("cpx_type") == "delINV"
