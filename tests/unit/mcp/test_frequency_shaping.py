from __future__ import annotations

import pytest

from gnomad_link.models import VariantDataSource, VariantFrequencyResponse
from gnomad_link.models.variant_models import PopulationFrequency


def _make_response() -> VariantFrequencyResponse:
    exome = VariantDataSource(
        ac=200,
        an=300_000,
        homozygote_count=2,
        populations=[
            PopulationFrequency.model_validate(
                {"id": "afr", "ac": 143, "an": 8_000, "homozygote_count": 2}
            ),
            PopulationFrequency.model_validate(
                {"id": "nfe", "ac": 7, "an": 150_000, "homozygote_count": 0}
            ),
            PopulationFrequency.model_validate(
                {"id": "non_topmed_afr", "ac": 80, "an": 5_000, "homozygote_count": 1}
            ),
            PopulationFrequency.model_validate(
                {"id": "afr_XX", "ac": 70, "an": 4_000, "homozygote_count": 1}
            ),
            PopulationFrequency.model_validate(
                {"id": "asj", "ac": 0, "an": 1_000, "homozygote_count": 0}
            ),
        ],
    )
    return VariantFrequencyResponse(
        variant_id="1-1-A-T", dataset="gnomad_r4", exome=exome, genome=None
    )


def test_default_shape_drops_zero_subcohort_and_sex_split() -> None:
    from gnomad_link.mcp.shaping import shape_variant_frequencies

    payload = shape_variant_frequencies(
        _make_response(),
        populations=None,
        include_subcohorts=False,
        include_sex_split=False,
        exclude_zero_populations=True,
    )

    pops = {p["id"] for p in payload["exome"]["populations"]}
    assert pops == {"afr", "nfe"}
    assert payload["exome"]["populations"][0]["af"] == pytest.approx(143 / 8_000)


def test_truncated_block_explains_what_was_dropped() -> None:
    from gnomad_link.mcp.shaping import shape_variant_frequencies

    payload = shape_variant_frequencies(
        _make_response(),
        populations=None,
        include_subcohorts=False,
        include_sex_split=False,
        exclude_zero_populations=True,
    )

    trunc = payload["exome"]["truncated"]
    assert trunc["kind"] == "populations"
    assert trunc["dropped"]["subcohorts"] == 1
    assert trunc["dropped"]["sex_split"] == 1
    assert trunc["dropped"]["zero_ac"] == 1
    assert "include_subcohorts" in trunc["to_disable"]


def test_populations_filter_restricts_rows() -> None:
    from gnomad_link.mcp.shaping import shape_variant_frequencies

    payload = shape_variant_frequencies(
        _make_response(),
        populations=["afr"],
        include_subcohorts=False,
        include_sex_split=False,
        exclude_zero_populations=True,
    )

    assert [p["id"] for p in payload["exome"]["populations"]] == ["afr"]


def test_include_subcohorts_keeps_prefixed_rows() -> None:
    from gnomad_link.mcp.shaping import shape_variant_frequencies

    payload = shape_variant_frequencies(
        _make_response(),
        populations=None,
        include_subcohorts=True,
        include_sex_split=False,
        exclude_zero_populations=True,
    )

    pops = {p["id"] for p in payload["exome"]["populations"]}
    assert "non_topmed_afr" in pops


def test_summary_ignores_subcohorts_even_if_included() -> None:
    """Subcohort rows like '1kg:msl' must never win the summary slot."""

    from gnomad_link.mcp.shaping import shape_variant_frequencies

    exome = VariantDataSource(
        ac=10,
        an=300_000,
        homozygote_count=0,
        populations=[
            PopulationFrequency.model_validate(
                {"id": "afr", "ac": 5, "an": 1_000, "homozygote_count": 0}
            ),
            # Subcohort with much higher AF than any base population
            PopulationFrequency.model_validate(
                {"id": "1kg:msl", "ac": 200, "an": 1_000, "homozygote_count": 5}
            ),
        ],
    )
    response = VariantFrequencyResponse(
        variant_id="1-1-A-T", dataset="gnomad_r4", exome=exome, genome=None
    )
    payload = shape_variant_frequencies(
        response,
        populations=None,
        include_subcohorts=True,  # subcohort row is visible in populations list
        include_sex_split=False,
        exclude_zero_populations=True,
    )

    assert payload["summary"]["top_enriched_population"]["id"] == "afr"


def test_summary_picks_highest_af_population() -> None:
    from gnomad_link.mcp.shaping import shape_variant_frequencies

    payload = shape_variant_frequencies(
        _make_response(),
        populations=None,
        include_subcohorts=False,
        include_sex_split=False,
        exclude_zero_populations=True,
    )

    top = payload["summary"]["top_enriched_population"]
    assert top["id"] == "afr"
    assert top["af"] == pytest.approx(143 / 8_000)
    assert top["source"] == "exome"


def test_summary_includes_overall_af_and_max_pop() -> None:
    from gnomad_link.mcp.shaping import shape_variant_frequencies

    payload = shape_variant_frequencies(
        _make_response(),
        populations=None,
        include_subcohorts=False,
        include_sex_split=False,
        exclude_zero_populations=True,
    )

    summary = payload["summary"]
    assert "overall_af" in summary
    assert summary["overall_af"] is not None
    assert "max_pop" in summary
    assert "max_pop_af" in summary
    assert summary["max_pop"] == "afr"
    # has_clinvar placeholder is None (unknown without get_clinvar_variant_details)
    assert "has_clinvar" in summary
    assert summary["has_clinvar"] is None


def test_gene_symbol_and_consequence_pass_through() -> None:
    from gnomad_link.mcp.shaping import shape_variant_frequencies

    response = VariantFrequencyResponse(
        variant_id="1-55051215-G-GA",
        dataset="gnomad_r4",
        exome=None,
        genome=None,
        gene_symbol="PCSK9",
        major_consequence="frameshift_variant",
    )

    payload = shape_variant_frequencies(
        response,
        populations=None,
        include_subcohorts=False,
        include_sex_split=False,
        exclude_zero_populations=True,
    )

    assert payload["gene_symbol"] == "PCSK9"
    assert payload["major_consequence"] == "frameshift_variant"
    assert "summary" not in payload  # no populations means no summary


class _StubFrequencyService:
    """Minimal FrequencyService stub returning a fixed VariantFrequencyResponse."""

    def __init__(self, response: VariantFrequencyResponse) -> None:
        self._response = response

    async def get_variant_frequencies(
        self, variant_id: str, dataset: str
    ) -> VariantFrequencyResponse:
        return self._response


@pytest.mark.asyncio
async def test_get_variant_frequencies_emits_next_commands_to_clinvar() -> None:
    """Tool wrapper injects a chain-of-thought hint pointing at ClinVar."""

    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub_response = VariantFrequencyResponse(
        variant_id="1-55051215-G-GA",
        dataset="gnomad_r4",
        exome=None,
        genome=None,
    )
    stub = _StubFrequencyService(stub_response)
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "get_variant_frequencies",
        {"variant_id": "1-55051215-G-GA", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    next_commands = payload.get("_meta", {}).get("next_commands", [])
    assert {
        "tool": "get_clinvar_variant_details",
        "arguments": {
            "variant_id": "1-55051215-G-GA",
            "reference_genome": "GRCh38",
        },
    } in next_commands
    # No frequency data -> headline says so plainly.
    assert payload["headline"] == "1-55051215-G-GA (gnomad_r4): no allele-frequency data."


@pytest.mark.asyncio
async def test_get_variant_frequencies_leads_with_headline() -> None:
    """A populated variant renders an AF headline at the top of the payload."""

    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub_response = VariantFrequencyResponse(
        variant_id="1-55051215-G-GA",
        dataset="gnomad_r4",
        major_consequence="missense_variant",
        exome=VariantDataSource(
            ac=10,
            an=20000,
            homozygote_count=0,
            populations=[
                PopulationFrequency(id="nfe", ac=9, an=12000, homozygote_count=0),
                PopulationFrequency(id="afr", ac=1, an=8000, homozygote_count=0),
            ],
        ),
        genome=None,
    )
    stub = _StubFrequencyService(stub_response)
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "get_variant_frequencies",
        {"variant_id": "1-55051215-G-GA", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    headline = payload["headline"]
    assert headline.startswith("1-55051215-G-GA missense_variant: AF ")
    assert "gnomad_r4" in headline
    assert "highest in nfe" in headline


@pytest.mark.asyncio
async def test_get_variant_frequencies_next_commands_uses_grch37_for_r2_1() -> None:
    """gnomad_r2_1 maps to GRCh37 in the ClinVar follow-up command."""

    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub_response = VariantFrequencyResponse(
        variant_id="1-55051215-G-GA",
        dataset="gnomad_r2_1",
        exome=None,
        genome=None,
    )
    stub = _StubFrequencyService(stub_response)
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "get_variant_frequencies",
        {"variant_id": "1-55051215-G-GA", "dataset": "gnomad_r2_1"},
    )
    payload = result.structured_content or {}

    next_commands = payload.get("_meta", {}).get("next_commands", [])
    assert {
        "tool": "get_clinvar_variant_details",
        "arguments": {
            "variant_id": "1-55051215-G-GA",
            "reference_genome": "GRCh37",
        },
    } in next_commands
