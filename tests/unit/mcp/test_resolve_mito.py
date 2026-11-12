"""resolve_variant_id must never return an empty success for a chrM id (#127).

gnomAD's variant_search does not index mitochondrial variants, so an MT-/M- id
used to come back as ``results: [], success: true`` -- indistinguishable from
"absent". The resolver now looks the id up in the dedicated mitochondrial
endpoint and routes follow-ups to get_mitochondrial_variant.
"""

from __future__ import annotations

from typing import Any

import pytest


class _MitoStub:
    def __init__(self) -> None:
        self.search_calls: list[str] = []
        self.mito_calls: list[tuple[str, str]] = []

    async def search_variants(self, query: str, dataset: str) -> list[str]:
        self.search_calls.append(query)
        return []

    async def get_mitochondrial_variant(self, variant_id: str, dataset: str) -> dict[str, Any]:
        self.mito_calls.append((variant_id, dataset))
        return {
            "mitochondrial_variant": {
                "variant_id": variant_id,
                "an": 56424,
                "ac_hom": 10,
                "ac_het": 2,
            }
        }


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", ["resolve_variant_id", "search_variants"])
@pytest.mark.parametrize("query", ["MT-616-T-C", "M-616-T-C", "chrM-616-t-c"])
async def test_mito_query_resolves_via_mitochondrial_endpoint(tool: str, query: str) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _MitoStub()
    mcp = create_gnomad_mcp(service_factory=lambda: stub)
    result = await mcp.call_tool(tool, {"query": query})
    payload = result.structured_content or {}

    assert payload.get("success") is not False, payload
    assert stub.search_calls == []
    assert stub.mito_calls == [("M-616-T-C", "gnomad_r4")]
    assert payload["total_count"] == 1
    first = payload["results"][0]
    assert first["variant_id"] == "M-616-T-C"
    assert first["variant_type"] == "mitochondrial"
    assert first["af_hom"] == pytest.approx(10 / 56424)
    assert first["af_het"] == pytest.approx(2 / 56424)
    nxt = payload["_meta"]["next_commands"]
    assert nxt[0] == {
        "tool": "get_mitochondrial_variant",
        "arguments": {"variant_id": "M-616-T-C", "dataset": "gnomad_r4"},
    }
    assert all(c["tool"] != "get_variant_frequencies" for c in nxt)
    assert "get_mitochondrial_variant" in payload["next_steps"][0]


@pytest.mark.asyncio
async def test_mito_query_on_r2_1_is_explicit_invalid_input() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _MitoStub()
    mcp = create_gnomad_mcp(service_factory=lambda: stub)
    result = await mcp.call_tool(
        "resolve_variant_id",
        {"query": "MT-616-T-C", "dataset": "gnomad_r2_1"},
    )
    payload = result.structured_content or {}

    assert payload["success"] is False
    assert payload["error_code"] == "invalid_input"
    assert "mitochondrial" in payload["message"]
    assert stub.mito_calls == []
