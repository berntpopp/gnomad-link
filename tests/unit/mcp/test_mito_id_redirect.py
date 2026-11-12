"""A mitochondrial id sent to an autosomal tool must redirect to get_mitochondrial_variant."""

from __future__ import annotations

import pytest

from gnomad_link.mcp.facade import create_gnomad_mcp

_AUTOSOMAL_TOOLS = [
    ("get_variant_frequencies", "variant_id"),
    ("get_variant_details", "variant_id"),
    ("compute_carrier_frequency", "variant_id"),
    ("compare_variant_across_datasets", "variant_id"),
    ("get_coverage", "target"),
]
_IDS = ["M-3243-A-G", "MT-3243-A-G", "chrM-3243-A-G"]


@pytest.mark.asyncio
@pytest.mark.parametrize("variant_id", _IDS)
@pytest.mark.parametrize(("tool", "param"), _AUTOSOMAL_TOOLS)
async def test_mito_id_redirects_to_mito_tool(tool: str, param: str, variant_id: str) -> None:
    args = {param: variant_id}
    if tool == "compute_carrier_frequency":
        args["inheritance"] = "AR"
    result = await create_gnomad_mcp(service_factory=lambda: object()).call_tool(tool, args)
    p = result.structured_content or {}

    assert p["error_code"] == "invalid_input", p
    assert "mitochondrial" in p["message"].lower() + p["recovery"].lower()
    assert p["fallback_tool"] == "get_mitochondrial_variant"
    assert p["fallback_args"] == {"variant_id": "M-3243-A-G"}
    assert p["_meta"]["next_commands"][0] == {
        "tool": "get_mitochondrial_variant",
        "arguments": {"variant_id": "M-3243-A-G"},
    }
