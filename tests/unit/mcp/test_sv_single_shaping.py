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
        "cpx_intervals": [{"type": "DEL", "chrom": "1"}],
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


@pytest.mark.asyncio
async def test_null_bearing_complex_sv_survives_output_validation() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp_instance = create_gnomad_mcp(service_factory=lambda: _SVStub())
    payload = await _invoke(mcp_instance, "get_structural_variant", {"variant_id": "CPX_chr1_1"})

    # The whole M-1 point: null end/af/ac/an must NOT trip output validation.
    assert payload.get("error_code") != "output_validation_failed", payload
    assert payload.get("variant_id") == "CPX_chr1_1", payload
    assert payload.get("cpx_type") == "delINV"
