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
