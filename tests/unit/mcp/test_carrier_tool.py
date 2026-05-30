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
    assert payload["overall"]["af_source"] == "exome"
    assert payload["overall"]["carrier_frequency"] == pytest.approx(0.044942, abs=1e-6)
    assert payload["overall"]["affected_frequency"] == pytest.approx(0.000529, abs=1e-6)
    assert payload["overall"]["affected_ci_low"] < payload["overall"]["affected_frequency"]
    assert payload["overall"]["affected_ci_high"] > payload["overall"]["affected_frequency"]
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
    assert by_pop["nfe"]["af_source"] == "exome"
    assert by_pop["nfe"]["carrier_frequency"] == pytest.approx(0.044942, abs=1e-6)
    # afr has ac == 0 -> carrier present but zero, row still emitted.
    assert by_pop["afr"]["af"] == pytest.approx(0.0, abs=1e-12)
    assert by_pop["afr"]["carrier_frequency"] == pytest.approx(0.0, abs=1e-12)
    assert by_pop["afr"]["affected_ci_low"] == pytest.approx(0.0, abs=1e-12)
    assert by_pop["afr"]["affected_ci_high"] > by_pop["afr"]["affected_frequency"]
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


def _ar_response_with_sex_split() -> VariantFrequencyResponse:
    return VariantFrequencyResponse(
        variant_id="7-117559590-ATCT-A",
        dataset="gnomad_r4",
        exome=VariantDataSource(
            ac=460,
            an=20000,
            homozygote_count=5,
            populations=[
                PopulationFrequency(id="nfe", ac=460, an=20000, homozygote_count=5),
                PopulationFrequency(id="afr", ac=20, an=8000, homozygote_count=0),
                # Sex-split pseudo-populations: must NOT appear for AR and must not
                # win the max-population pick (regression for F5).
                PopulationFrequency(id="XX", ac=300, an=11000, homozygote_count=3),
                PopulationFrequency(id="XY", ac=160, an=9000, homozygote_count=2),
                PopulationFrequency(id="nfe_XX", ac=290, an=10000, homozygote_count=3),
                PopulationFrequency(id="nfe_XY", ac=170, an=10000, homozygote_count=2),
            ],
        ),
        genome=None,
        gene_symbol="CFTR",
        major_consequence="frameshift_variant",
    )


@pytest.mark.asyncio
async def test_ar_suppresses_sex_split_rows_and_adds_per_pop_ci() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _StubFreqService(_ar_response_with_sex_split())
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool(
        "compute_carrier_frequency",
        {"variant_id": "7-117559590-ATCT-A", "inheritance": "AR"},
    )
    payload = result.structured_content or {}

    pops = {row["population"] for row in payload["per_population"]}
    assert pops == {"nfe", "afr"}  # no XX/XY/nfe_XX/nfe_XY
    # The max-population pick (and thus the headline) is a real ancestry, not nfe_XX.
    assert payload["summary"]["max_carrier_frequency_population"] == "nfe"
    assert "_XX" not in payload["headline"] and "_XY" not in payload["headline"]
    # Per-population rows now carry Wilson CIs for parity with the overall block.
    nfe = next(r for r in payload["per_population"] if r["population"] == "nfe")
    assert nfe["ci_low"] is not None and nfe["ci_high"] is not None
    assert nfe["ci_low"] < nfe["carrier_frequency"] < nfe["ci_high"]


@pytest.mark.asyncio
async def test_compute_carrier_frequency_leads_with_headline() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _StubFreqService(_ar_response())
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool(
        "compute_carrier_frequency",
        {"variant_id": "7-117559590-ATCT-A", "inheritance": "AR"},
    )
    payload = result.structured_content or {}

    headline = payload["headline"]
    assert headline.startswith("7-117559590-ATCT-A (AR/gnomad_r4): carrier frequency")
    assert "highest in nfe" in headline
    # Compact (default) carries a citations_ref pointer and short citations.
    assert payload["citations_ref"] == "gnomad://citations"


@pytest.mark.asyncio
async def test_compute_carrier_frequency_full_mode_inlines_full_citations() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _StubFreqService(_ar_response())
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    compact = (
        await mcp.call_tool(
            "compute_carrier_frequency",
            {"variant_id": "7-117559590-ATCT-A", "inheritance": "AR"},
        )
    ).structured_content or {}
    full = (
        await mcp.call_tool(
            "compute_carrier_frequency",
            {
                "variant_id": "7-117559590-ATCT-A",
                "inheritance": "AR",
                "response_mode": "full",
            },
        )
    ).structured_content or {}

    # full inlines bibliographic detail (DOIs) that compact omits.
    assert not any("doi:" in c for c in compact["citations"])
    assert any("doi:" in c for c in full["citations"])
    assert full["citations_ref"] == "gnomad://citations"


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


def _ad_response() -> VariantFrequencyResponse:
    # q = 0.011 (ac=220, an=20000).
    return VariantFrequencyResponse(
        variant_id="17-43044295-A-G",
        dataset="gnomad_r4",
        exome=VariantDataSource(
            ac=220,
            an=20000,
            homozygote_count=0,
            populations=[PopulationFrequency(id="nfe", ac=220, an=20000, homozygote_count=0)],
        ),
        genome=None,
        gene_symbol="BRCA1",
        major_consequence="missense_variant",
    )


def _xl_response() -> VariantFrequencyResponse:
    # Sex-split rows: XX (q_XX=0.01) and XY (q_XY=0.02), plus ancestry+sex rows.
    return VariantFrequencyResponse(
        variant_id="X-153296777-C-T",
        dataset="gnomad_r4",
        exome=VariantDataSource(
            ac=300,
            an=20000,
            homozygote_count=0,
            hemizygote_count=100,
            populations=[
                PopulationFrequency(id="XX", ac=100, an=10000, homozygote_count=0),
                PopulationFrequency(id="XY", ac=200, an=10000, homozygote_count=0),
                PopulationFrequency(id="nfe_XX", ac=60, an=6000, homozygote_count=0),
                PopulationFrequency(id="nfe_XY", ac=120, an=6000, homozygote_count=0),
            ],
        ),
        genome=None,
        gene_symbol="F8",
        major_consequence="missense_variant",
    )


@pytest.mark.asyncio
async def test_compute_carrier_frequency_ad_affected_or_carrier() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _StubFreqService(_ad_response())
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool(
        "compute_carrier_frequency",
        {"variant_id": "17-43044295-A-G", "inheritance": "AD"},
    )
    payload = result.structured_content or {}

    # AD overall: 1 - (1 - 0.011)^2 == 2*0.011 - 0.011^2 == 0.021879.
    assert payload["inheritance"] == "AD"
    assert payload["overall"]["af_source"] == "exome"
    assert payload["overall"]["affected_or_carrier_frequency"] == pytest.approx(0.021879, abs=1e-6)
    assert payload["overall"]["ci_low"] < payload["overall"]["affected_or_carrier_frequency"]
    assert payload["overall"]["ci_high"] > payload["overall"]["affected_or_carrier_frequency"]
    row = payload["per_population"][0]
    assert row["af_source"] == "exome"
    assert "carrier_frequency" not in row
    assert row["affected_or_carrier_frequency"] == pytest.approx(0.021879, abs=1e-6)
    assert payload["summary"]["max_carrier_frequency_population"] == "nfe"


@pytest.mark.asyncio
async def test_compute_carrier_frequency_xl_sex_split() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _StubFreqService(_xl_response())
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool(
        "compute_carrier_frequency",
        {"variant_id": "X-153296777-C-T", "inheritance": "XL"},
    )
    payload = result.structured_content or {}

    assert payload["inheritance"] == "XL"
    # Overall q_XX = 0.01 -> female_carrier = 0.02, affected_female = 0.0001.
    assert payload["overall"]["female_carrier_frequency"] == pytest.approx(0.02, abs=1e-9)
    assert payload["overall"]["affected_female_frequency"] == pytest.approx(0.0001, abs=1e-9)
    # q_XY = 0.02 -> hemizygous affected male = 0.02 (no 2x, no square).
    assert payload["overall"]["affected_male_frequency"] == pytest.approx(0.02, abs=1e-9)
    # Ancestry rows are sex-split: nfe -> female_carrier from nfe_XX (q=0.01) = 0.02.
    by_pop = {row["population"]: row for row in payload["per_population"]}
    assert by_pop["nfe"]["female_carrier_frequency"] == pytest.approx(0.02, abs=1e-9)
    assert by_pop["nfe"]["affected_male_frequency"] == pytest.approx(0.02, abs=1e-9)


@pytest.mark.asyncio
async def test_compute_carrier_frequency_xl_missing_sex_rows_yields_none() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    response = VariantFrequencyResponse(
        variant_id="X-153296777-C-T",
        dataset="gnomad_r4",
        exome=VariantDataSource(
            ac=10,
            an=10000,
            homozygote_count=0,
            populations=[PopulationFrequency(id="nfe", ac=10, an=10000, homozygote_count=0)],
        ),
        genome=None,
    )
    service = _StubFreqService(response)
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool(
        "compute_carrier_frequency",
        {"variant_id": "X-153296777-C-T", "inheritance": "XL"},
    )
    payload = result.structured_content or {}

    # No XX/XY rows present -> sex-split estimates undefined, not zero.
    assert payload["overall"]["female_carrier_frequency"] is None
    assert payload["overall"]["affected_male_frequency"] is None
