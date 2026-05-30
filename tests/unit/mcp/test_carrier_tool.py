from __future__ import annotations

import pytest

from gnomad_link.models import (
    PopulationFrequency,
    VariantDataSource,
    VariantFrequencyResponse,
)


def _ar_response() -> VariantFrequencyResponse:
    # CFTR-like overall q = 0.023 (ac=460, an=20000), one population row.
    return VariantFrequencyResponse(
        variant_id="7-117559590-ATCT-A",
        dataset="gnomad_r4",
        exome=VariantDataSource(
            ac=460,
            an=20000,
            homozygote_count=5,
            populations=[
                PopulationFrequency(id="nfe", ac=460, an=20000, homozygote_count=5),
                PopulationFrequency(id="afr", ac=0, an=8000, homozygote_count=0),
            ],
        ),
        genome=None,
        gene_symbol="CFTR",
        major_consequence="frameshift_variant",
    )


class _StubFreqService:
    def __init__(self, response: VariantFrequencyResponse) -> None:
        self._response = response
        self.calls: list[tuple[str, str]] = []

    async def get_variant_frequencies(
        self, variant_id: str, dataset: str = "gnomad_r4"
    ) -> VariantFrequencyResponse:
        self.calls.append((variant_id, dataset))
        return self._response


@pytest.mark.asyncio
async def test_compute_carrier_frequency_ar_overall_golden() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _StubFreqService(_ar_response())
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool(
        "compute_carrier_frequency",
        {"variant_id": "7-117559590-ATCT-A", "inheritance": "AR"},
    )
    payload = result.structured_content or {}

    assert payload["inheritance"] == "AR"
    assert payload["overall"]["af"] == pytest.approx(0.023, abs=1e-6)
    assert payload["overall"]["carrier_frequency"] == pytest.approx(0.044942, abs=1e-6)
    assert payload["overall"]["affected_frequency"] == pytest.approx(0.000529, abs=1e-6)
    # Wilson CI present and brackets the point estimate.
    assert payload["overall"]["ci_low"] < payload["overall"]["carrier_frequency"]
    assert payload["overall"]["ci_high"] > payload["overall"]["carrier_frequency"]


@pytest.mark.asyncio
async def test_compute_carrier_frequency_per_population_and_summary() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _StubFreqService(_ar_response())
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool(
        "compute_carrier_frequency",
        {"variant_id": "7-117559590-ATCT-A", "inheritance": "AR"},
    )
    payload = result.structured_content or {}

    by_pop = {row["population"]: row for row in payload["per_population"]}
    assert by_pop["nfe"]["carrier_frequency"] == pytest.approx(0.044942, abs=1e-6)
    # afr has ac == 0 -> carrier present but zero, row still emitted.
    assert by_pop["afr"]["af"] == pytest.approx(0.0, abs=1e-12)
    assert by_pop["afr"]["carrier_frequency"] == pytest.approx(0.0, abs=1e-12)
    assert payload["summary"]["max_carrier_frequency_population"] == "nfe"


@pytest.mark.asyncio
async def test_compute_carrier_frequency_hom_corrected_method() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _StubFreqService(_ar_response())
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool(
        "compute_carrier_frequency",
        {
            "variant_id": "7-117559590-ATCT-A",
            "inheritance": "AR",
            "method": "hom_corrected",
        },
    )
    payload = result.structured_content or {}

    # nfe: (460 - 2*5) / (20000/2) = 450 / 10000 = 0.045
    by_pop = {row["population"]: row for row in payload["per_population"]}
    assert by_pop["nfe"]["carrier_frequency"] == pytest.approx(0.045, abs=1e-9)
    assert payload["method"] == "hom_corrected"


@pytest.mark.asyncio
async def test_compute_carrier_frequency_zero_an_yields_none_carrier() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    response = VariantFrequencyResponse(
        variant_id="7-117559590-ATCT-A",
        dataset="gnomad_r4",
        exome=VariantDataSource(
            ac=0,
            an=0,
            homozygote_count=0,
            populations=[PopulationFrequency(id="nfe", ac=0, an=0, homozygote_count=0)],
        ),
        genome=None,
    )
    service = _StubFreqService(response)
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool(
        "compute_carrier_frequency",
        {"variant_id": "7-117559590-ATCT-A", "inheritance": "AR"},
    )
    payload = result.structured_content or {}

    assert payload["overall"]["carrier_frequency"] is None
    assert payload["overall"]["ci_low"] is None
    assert payload["overall"]["ci_high"] is None


@pytest.mark.asyncio
async def test_compute_carrier_frequency_emits_citations_and_assumptions() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _StubFreqService(_ar_response())
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool(
        "compute_carrier_frequency",
        {"variant_id": "7-117559590-ATCT-A", "inheritance": "AR"},
    )
    payload = result.structured_content or {}

    assert any("Schrodi" in c for c in payload["citations"])
    assert "Hardy-Weinberg" in payload["assumptions_note"]
    assert payload["_meta"]["unsafe_for_clinical_use"] is True


@pytest.mark.asyncio
async def test_compute_carrier_frequency_emits_next_commands() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _StubFreqService(_ar_response())
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool(
        "compute_carrier_frequency",
        {"variant_id": "7-117559590-ATCT-A", "inheritance": "AR"},
    )
    payload = result.structured_content or {}

    next_tools = {cmd["tool"] for cmd in payload["_meta"]["next_commands"]}
    assert next_tools == {"get_clinvar_variant_details", "get_variant_frequencies"}
    # No self-reference.
    assert "compute_carrier_frequency" not in next_tools
