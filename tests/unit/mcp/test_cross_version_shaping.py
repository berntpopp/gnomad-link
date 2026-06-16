"""Cross-version frequency/variant shaping (issue #5, C2).

Deterministic, no-network characterization of how the pure shaping helpers
handle the structurally divergent payloads of the three gnomAD versions:

  * gnomad_r2_1 (v2, GRCh37): exome + genome present.
  * gnomad_r3   (v3, GRCh38): genome-only (no exome source).
  * gnomad_r4   (v4, GRCh38): exome + genome present, in_silico_predictors and
    hemizygote_count carried through.

Follows the existing ``test_frequency_shaping.py`` pattern: call the shaping
functions directly on synthetic, minimal, inline per-version payloads. No
``respx`` / network is used, matching that file. The load-bearing assertion in
each test is a field that differs across versions (the genome-only v3 source
selection; the absent-vs-present in_silico_predictors block).
"""

from __future__ import annotations

import pytest

from gnomad_link.mcp.shaping import (
    shape_variant_details_compact,
    shape_variant_frequencies,
)
from gnomad_link.models import VariantDataSource, VariantFrequencyResponse
from gnomad_link.models.variant_models import PopulationFrequency


def _source(ac: int, an: int, pops: list[tuple[str, int, int]]) -> VariantDataSource:
    return VariantDataSource(
        ac=ac,
        an=an,
        homozygote_count=0,
        populations=[
            PopulationFrequency.model_validate(
                {"id": pid, "ac": pac, "an": pan, "homozygote_count": 0}
            )
            for pid, pac, pan in pops
        ],
    )


def _response_for_version(version: str, dataset: str) -> VariantFrequencyResponse:
    """Build a minimal per-version response mirroring real gnomAD source availability.

    v3 is genome-only; v2/v4 carry both exome and genome. Exome AN is set larger
    than genome AN for v2/v4 so the preferred-overall-AF source selection
    (largest AN wins) is exercised across the version axis.
    """
    genome = _source(60, 1_000, [("nfe", 50, 800), ("afr", 10, 200)])
    if version == "v3":
        # gnomAD v3 has no exome subset.
        return VariantFrequencyResponse(
            variant_id="1-55051215-G-GA", dataset=dataset, exome=None, genome=genome
        )
    exome = _source(5, 20_000, [("nfe", 4, 15_000), ("afr", 1, 5_000)])
    return VariantFrequencyResponse(
        variant_id="1-55051215-G-GA", dataset=dataset, exome=exome, genome=genome
    )


VERSION_DATASET = [
    ("v2", "gnomad_r2_1"),
    ("v3", "gnomad_r3"),
    ("v4", "gnomad_r4"),
]


@pytest.mark.parametrize("version,dataset", VERSION_DATASET)
def test_dataset_passes_through_unchanged(version: str, dataset: str) -> None:
    """The shaped payload echoes the requested dataset verbatim for every version."""
    payload = shape_variant_frequencies(
        _response_for_version(version, dataset),
        populations=None,
        include_subcohorts=False,
        include_sex_split=False,
        exclude_zero_populations=True,
    )
    assert payload["dataset"] == dataset


@pytest.mark.parametrize("version,dataset", VERSION_DATASET)
def test_genome_only_v3_has_no_exome_block(version: str, dataset: str) -> None:
    """v3 (genome-only) shapes to exome=None; v2/v4 produce a populated exome block.

    This is the headline structural divergence: gnomAD v3 ships genomes only, so
    the exome source is absent and the shaper must emit ``exome: None`` rather
    than fabricating an empty block.
    """
    payload = shape_variant_frequencies(
        _response_for_version(version, dataset),
        populations=None,
        include_subcohorts=False,
        include_sex_split=False,
        exclude_zero_populations=True,
    )
    if version == "v3":
        assert payload["exome"] is None
    else:
        assert payload["exome"] is not None
        assert payload["exome"]["an"] == 20_000
    # Genome is present in all three versions.
    assert payload["genome"] is not None
    assert payload["genome"]["an"] == 1_000


@pytest.mark.parametrize("version,dataset", VERSION_DATASET)
def test_overall_af_source_selection_per_version(version: str, dataset: str) -> None:
    """overall_af_source is the largest-AN source: genome for v3, exome for v2/v4.

    The fixtures set exome AN (20_000) > genome AN (1_000) for v2/v4, so exome
    wins; v3 has no exome so genome wins by default.
    """
    payload = shape_variant_frequencies(
        _response_for_version(version, dataset),
        populations=None,
        include_subcohorts=False,
        include_sex_split=False,
        exclude_zero_populations=True,
    )
    summary = payload["summary"]
    if version == "v3":
        assert summary["overall_af_source"] == "genome"
        assert summary["overall_af"] == pytest.approx(60 / 1_000)
    else:
        assert summary["overall_af_source"] == "exome"
        assert summary["overall_af"] == pytest.approx(5 / 20_000)


@pytest.mark.parametrize("version,dataset", VERSION_DATASET)
def test_top_enriched_population_is_base_code_each_version(version: str, dataset: str) -> None:
    """The summary's top population is a base population code in every version."""
    payload = shape_variant_frequencies(
        _response_for_version(version, dataset),
        populations=None,
        include_subcohorts=False,
        include_sex_split=False,
        exclude_zero_populations=True,
    )
    top = payload["summary"]["top_enriched_population"]
    assert top["id"] in {"nfe", "afr"}
    # For v3 the top population can only come from the genome source.
    if version == "v3":
        assert top["source"] == "genome"


def _details_for_version(version: str) -> dict:
    """A raw variant-details GraphQL dict shaped like the per-version variant.graphql.

    v2 omits the in_silico_predictors block (its variant.graphql does not request
    it); v3/v4 include it. Hemizygote_count is carried on v4-style exome sources.
    """
    raw: dict = {
        "variant_id": "1-55051215-G-GA",
        "reference_genome": "GRCh37" if version == "v2" else "GRCh38",
        "pos": 55051215,
        "ref": "G",
        "alt": "GA",
        "major_consequence": "frameshift_variant",
        "transcript_consequences": [
            {"canonical": True, "gene_symbol": "PCSK9", "biotype": "protein_coding"}
        ],
        "genome": {
            "ac": 10,
            "an": 1_000,
            "homozygote_count": 0,
            "populations": [{"id": "nfe", "ac": 10, "an": 1_000, "homozygote_count": 0}],
        },
    }
    if version != "v3":
        # v2 + v4 carry an exome source; v4 additionally carries hemizygote_count.
        exome: dict = {
            "ac": 5,
            "an": 20_000,
            "homozygote_count": 0,
            "populations": [{"id": "nfe", "ac": 5, "an": 20_000, "homozygote_count": 0}],
        }
        if version == "v4":
            exome["hemizygote_count"] = 0
        raw["exome"] = exome
    if version != "v2":
        # v3 + v4 variant documents request in_silico_predictors.
        raw["in_silico_predictors"] = [{"id": "cadd", "value": "23.1"}]
    return raw


@pytest.mark.parametrize("version", ["v2", "v3", "v4"])
def test_variant_details_in_silico_only_v3_v4(version: str) -> None:
    """shape_variant_details_compact keeps in_silico_predictors only when present.

    The compact projector's ``keep`` set includes in_silico_predictors, so a v2
    payload (which never carries that block) yields a compact dict without it,
    while v3/v4 payloads keep it. This characterizes the version divergence
    surviving the compaction step rather than being injected by it.
    """
    compact = shape_variant_details_compact(_details_for_version(version))
    if version == "v2":
        assert "in_silico_predictors" not in compact
    else:
        assert compact["in_silico_predictors"] == [{"id": "cadd", "value": "23.1"}]


@pytest.mark.parametrize("version", ["v2", "v3", "v4"])
def test_variant_details_exome_presence_per_version(version: str) -> None:
    """v3 compact details carry only genome; v2/v4 carry exome too."""
    compact = shape_variant_details_compact(_details_for_version(version))
    assert "genome" in compact
    if version == "v3":
        assert "exome" not in compact
    else:
        assert "exome" in compact
