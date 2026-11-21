"""#151: a wrong variant-id shape must reach the server, which names the next call.

Clients validate against the advertised ``pattern`` and show only a bare regex error,
so the variant-id fields hide it from the schema (``hide_pattern``); pydantic still
enforces it server-side.
"""

from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.mcp.facade import create_gnomad_mcp

VARIANT_TOOLS = {
    "get_variant_frequencies": "variant_id",
    "get_variant_details": "variant_id",
    "get_clinvar_variant_details": "variant_id",
    "compute_carrier_frequency": "variant_id",
    "compare_variant_across_datasets": "variant_id",
    "compute_variant_liftover": "source_variant_id",
}


def _mcp() -> Any:
    return create_gnomad_mcp(service_factory=lambda: object())


@pytest.mark.asyncio
async def test_variant_id_params_advertise_no_pattern() -> None:
    tools = {t.name: t for t in await _mcp().list_tools()}
    for tool, param in VARIANT_TOOLS.items():
        prop = tools[tool].parameters["properties"][param]
        assert "pattern" not in prop, tool
        assert "CHROM-POS-REF-ALT" in prop["description"], tool
    for tool in ("get_structural_variant", "get_mitochondrial_variant"):
        assert "pattern" not in tools[tool].parameters["properties"]["variant_id"], tool


@pytest.mark.parametrize(
    ("value", "next_call"),
    [
        ("587779817", ("resolve_variant_id", {"query": "rs587779817"})),
        (587779817, ("resolve_variant_id", {"query": "rs587779817"})),
        ("chr17-7674232-g-a", ("resolve_variant_id", {"query": "17-7674232-G-A"})),
        ("17:7674232 G>A", ("resolve_variant_id", {"query": "17-7674232-G-A"})),
        (
            "12-102843751-AGA-",
            (
                "vep_recode_variant",
                {"variants": ["12:g.102843751_102843753del"], "fields": "vcf_string"},
            ),
        ),
        (
            "NM_000314.8:c.212G>A",
            (
                "vep_recode_variant",
                {"variants": ["NM_000314.8:c.212G>A"], "fields": "vcf_string"},
            ),
        ),
        ("not-a-variant", ("resolve_variant_id", {"query": "not-a-variant"})),
    ],
)
@pytest.mark.asyncio
async def test_wrong_shape_names_field_form_and_next_call(
    value: object, next_call: tuple[str, dict[str, Any]]
) -> None:
    for tool, param in VARIANT_TOOLS.items():
        result = await _mcp().call_tool(tool, {param: value})
        payload = result.structured_content or {}
        assert payload["error_code"] == "invalid_input", (tool, payload)
        assert payload["field"] == param, (tool, payload)
        assert "CHROM-POS-REF-ALT" in payload["message"] + payload["recovery"], tool
        assert any(fe["field"] == param for fe in payload["field_errors"]), tool
        first = payload["_meta"]["next_commands"][0]
        assert (first["tool"], first["arguments"]) == next_call, (tool, first)
        assert (payload["fallback_tool"], payload["fallback_args"]) == next_call, tool


@pytest.mark.asyncio
async def test_non_ascii_input_is_not_echoed_into_a_call() -> None:
    result = await _mcp().call_tool("get_variant_frequencies", {"variant_id": "17-7674232-G-A‮"})
    payload = result.structured_content or {}
    assert payload["error_code"] == "invalid_input"
    assert payload["field"] == "variant_id"
    assert "‮" not in str(payload)


@pytest.mark.asyncio
async def test_sv_tool_gets_no_variant_resolver_hint() -> None:
    """A CHROM-POS-REF-ALT id on the SV tool is not resolve_variant_id's to answer."""
    result = await _mcp().call_tool("get_structural_variant", {"variant_id": "17-7674232-G-A"})
    payload = result.structured_content or {}
    assert payload["error_code"] == "invalid_input"
    assert "resolve_variant_id" not in str(payload["_meta"]["next_commands"])
