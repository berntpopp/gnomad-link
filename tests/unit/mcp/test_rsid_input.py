"""get_variant_frequencies / get_variant_details accept an rsID (router #319)."""

from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.mcp.facade import create_gnomad_mcp
from gnomad_link.models import VariantDataSource, VariantFrequencyResponse
from gnomad_link.models.variant_models import PopulationFrequency


class _Stub:
    def __init__(self, ids: list[str]) -> None:
        self.ids = ids
        self.freq_calls: list[str] = []

    async def search_variants(self, query: str, dataset: str = "gnomad_r4") -> list[str]:
        return list(self.ids)

    async def get_variant_frequencies(
        self, variant_id: str, dataset: str = "gnomad_r4"
    ) -> VariantFrequencyResponse:
        self.freq_calls.append(variant_id)
        exome = VariantDataSource(
            ac=7,
            an=189_000,
            populations=[PopulationFrequency(id="nfe", ac=7, an=189_000, homozygote_count=0)],
        )
        return VariantFrequencyResponse(
            variant_id=variant_id, dataset=dataset, exome=exome, genome=None
        )


async def _call(stub: _Stub, tool: str = "get_variant_frequencies") -> dict[str, Any]:
    mcp = create_gnomad_mcp(service_factory=lambda: stub)
    result = await mcp.call_tool(tool, {"variant_id": "rs11591147"})
    return result.structured_content or {}


@pytest.mark.asyncio
async def test_rsid_returns_frequencies_in_one_call_with_resolved_from() -> None:
    stub = _Stub(["1-55039974-G-T"])
    payload = await _call(stub)
    assert payload["success"] is True, payload
    assert stub.freq_calls == ["1-55039974-G-T"]
    assert payload["resolved_from"] == {
        "input": "rs11591147",
        "form": "rsid",
        "resolved_to": "1-55039974-G-T",
    }
    assert payload["exome"]


@pytest.mark.asyncio
async def test_multiallelic_rsid_is_ambiguous_with_candidates() -> None:
    stub = _Stub(["1-55039974-G-T", "1-55039974-G-A"])
    payload = await _call(stub)
    assert payload["error_code"] == "ambiguous_query"
    assert payload["candidates"] == ["1-55039974-G-T", "1-55039974-G-A"]
    assert payload["_meta"]["next_commands"][0]["tool"] == "resolve_variant_id"
    assert "rs11591147" not in payload["message"]
    assert stub.freq_calls == []


@pytest.mark.asyncio
async def test_unknown_rsid_is_not_found_pointing_at_resolver() -> None:
    payload = await _call(_Stub([]), tool="get_variant_details")
    assert payload["error_code"] == "not_found"
    assert payload["fallback_tool"] == "resolve_variant_id"
    assert payload["fallback_args"]["query"] == "rs11591147"


@pytest.mark.asyncio
async def test_non_rsid_free_text_still_rejected() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _Stub([]))
    result = await mcp.call_tool("get_variant_frequencies", {"variant_id": "BRCA1 c.68_69del"})
    assert (result.structured_content or {})["error_code"] == "invalid_input"
