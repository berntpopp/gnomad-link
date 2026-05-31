"""Task 12 (Phase 4a): response_mode='minimal' for the six headline tools.

Each test, per tool:
  1. asserts the minimal payload keeps headline (where applicable), the global/
     summary block, a full _meta (non-empty next_commands + unsafe_for_clinical_use),
     and a `truncated` block with to_restore == "response_mode='compact'";
  2. asserts the minimal payload DROPS the heavy arrays;
  3. asserts a MEASURED byte reduction vs compact for the same input; and
  4. asserts the compact (and, where it already existed, full) payload is
     byte-for-byte UNCHANGED -- captured by comparing the same canned input's
     compact/full payload against the structural invariants the pre-change tools
     guaranteed (per-pop arrays, transcripts, contributing list, etc. all present).

The stubs copy canned shapes from the per-tool unit suites (test_carrier_tool,
test_gene_carrier_tool, test_gene_summary_tool, test_compare_variant,
test_gene_details_headline, test_variant_details_population_trim).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from gnomad_link.mcp.facade import create_gnomad_mcp
from gnomad_link.models import (
    PopulationFrequency,
    VariantDataSource,
    VariantFrequencyResponse,
)
from gnomad_link.models.gene_models import Gene, GeneConstraint, GeneExon, GeneTranscript

_RESTORE = "response_mode='compact'"


def _structured(result: Any) -> dict[str, Any]:
    return result.structured_content or {}


def _bytes(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, default=str))


def _assert_minimal_envelope(
    payload: dict[str, Any], *, dropped: list[str], expects_headline: bool = True
) -> None:
    """Shared minimal-mode invariants (groundability + truncated block)."""
    if expects_headline:
        assert isinstance(payload.get("headline"), str) and payload["headline"].strip(), payload
    meta = payload.get("_meta")
    assert isinstance(meta, dict), payload
    nc = meta.get("next_commands")
    assert isinstance(nc, list) and nc, meta
    assert meta.get("unsafe_for_clinical_use") is True, meta
    trunc = payload.get("truncated")
    assert isinstance(trunc, dict), payload
    assert trunc.get("kind") == "minimal_mode", trunc
    assert trunc.get("to_restore") == _RESTORE, trunc
    for name in dropped:
        assert name in trunc.get("dropped", []), trunc


# ---------------------------------------------------------------------------
# Stubs (canned shapes copied from the per-tool unit suites)
# ---------------------------------------------------------------------------


def _freq_response() -> VariantFrequencyResponse:
    return VariantFrequencyResponse(
        variant_id="7-117559590-ATCT-A",
        dataset="gnomad_r4",
        exome=VariantDataSource(
            ac=460,
            an=20000,
            homozygote_count=5,
            populations=[
                PopulationFrequency(id="nfe", ac=460, an=20000, homozygote_count=5),
                PopulationFrequency(id="afr", ac=10, an=8000, homozygote_count=0),
            ],
        ),
        genome=None,
        gene_symbol="CFTR",
        major_consequence="frameshift_variant",
    )


class _FreqStub:
    async def get_variant_frequencies(
        self, variant_id: str, dataset: str = "gnomad_r4"
    ) -> VariantFrequencyResponse:
        return _freq_response()


def _pcsk9_gene() -> Gene:
    return Gene(
        gene_id="ENSG00000169174",
        symbol="PCSK9",
        name="proprotein convertase subtilisin/kexin type 9",
        canonical_transcript_id="ENST00000302118",
        chrom="1",
        start=55039447,
        stop=55064852,
        strand="+",
        gnomad_constraint=GeneConstraint(pli=0.0042, oe_lof=0.83),
        transcripts=[GeneTranscript(transcript_id="ENST1", chrom="1", start=1, stop=2)],
        exons=[GeneExon(feature_type="CDS", start=1, stop=2)],
    )


class _GeneStub:
    async def get_gene(
        self,
        *,
        gene_id: str | None = None,
        gene_symbol: str | None = None,
        reference_genome: str = "GRCh38",
    ) -> Gene:
        return _pcsk9_gene()


class _GeneSummaryStub:
    async def get_gene_summary(
        self,
        *,
        gene_id: str | None = None,
        gene_symbol: str | None = None,
        dataset: str = "gnomad_r4",
        include_expression: bool = True,
    ) -> dict[str, Any]:
        return {
            "gene_id": "ENSG00000169174",
            "symbol": "PCSK9",
            "name": "proprotein convertase subtilisin/kexin type 9",
            "coords": {"chrom": "1", "start": 55039447, "stop": 55064852},
            "dataset": dataset,
            "reference_genome": "GRCh38",
            "constraint": {"pli": 0.01, "oe_lof": 0.8},
            "canonical_transcript_id": "ENST00000302118",
            "mane_select_transcript": {"ensembl_id": "ENST00000302118", "refseq_id": "NM_174936"},
            "clinvar_variants": [
                {
                    "variant_id": "1-1-A-G",
                    "clinical_significance": "Pathogenic",
                    "gold_stars": 3,
                    "major_consequence": "missense_variant",
                },
                {
                    "variant_id": "1-2-A-G",
                    "clinical_significance": "Likely pathogenic",
                    "gold_stars": 1,
                    "major_consequence": "missense_variant",
                },
                {
                    "variant_id": "1-3-A-G",
                    "clinical_significance": "Benign",
                    "gold_stars": 2,
                    "major_consequence": "synonymous_variant",
                },
            ],
            "pext": {"flags": [], "regions": []},
            "expression": {
                "source_build": "GRCh37",
                "mean_pext": 0.7,
                "top_tissues": [{"tissue": "Liver", "value": 42.0}],
            },
            "flags": [],
            "partial": False,
        }


def _carrier_metrics(cf: float, sum_af: float) -> dict[str, Any]:
    return {
        "carrier_frequency": cf,
        "sum_af": sum_af,
        "total_ac": 100,
        "max_an": 10000,
        "genetic_prevalence": sum_af * sum_af,
        "bayesian_prevalence": sum_af * sum_af,
        "method": "hom_exclusion",
    }


class _GeneCarrierStub:
    async def get_gene_carrier_frequency(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "gene": {"gene_id": "ENSG1", "symbol": "CFTR"},
            "dataset": kwargs.get("dataset", "gnomad_r4"),
            "reference_genome": "GRCh38",
            "settings": {"method": kwargs.get("method", "hom_exclusion")},
            "global": _carrier_metrics(0.0568, 0.029157),
            "populations": {
                "afr": _carrier_metrics(0.0228, 0.01127),
                "nfe": _carrier_metrics(0.0631, 0.031837),
                "asj": _carrier_metrics(0.1106, 0.055357),
            },
            "qualifying_variants": [
                {"variant_id": "7-1-A-T", "global_af": 0.01},
                {"variant_id": "7-2-A-T", "global_af": 0.005},
            ],
            "qualifying_count": 523,
            "sources": {"plof_only": 121, "clinvar_only": 156, "both": 246},
        }


def _compare_freq(variant_id: str, dataset: str) -> VariantFrequencyResponse:
    return VariantFrequencyResponse(
        variant_id=variant_id,
        dataset=dataset,
        gene_symbol="HFE",
        major_consequence="missense_variant",
        exome=VariantDataSource(
            ac=200,
            an=100_000,
            homozygote_count=0,
            populations=[
                PopulationFrequency.model_validate(
                    {"id": "nfe", "ac": 10, "an": 50_000, "homozygote_count": 0}
                ),
                PopulationFrequency.model_validate(
                    {"id": "afr", "ac": 100, "an": 10_000, "homozygote_count": 0}
                ),
            ],
        ),
        genome=None,
    )


class _CompareStub:
    def __init__(self) -> None:
        self._freq = {
            "gnomad_r4": _compare_freq("6-26092913-G-A", "gnomad_r4"),
            "gnomad_r2_1": _compare_freq("6-26093141-G-A", "gnomad_r2_1"),
        }
        self._lift = [
            {
                "source": {"variant_id": "6-26093141-G-A", "reference_genome": "GRCh37"},
                "liftover": {"variant_id": "6-26092913-G-A", "reference_genome": "GRCh38"},
                "datasets": ["gnomad_r2_1", "gnomad_r4"],
            }
        ]

    async def get_variant_frequencies(
        self, variant_id: str, dataset: str
    ) -> VariantFrequencyResponse:
        return self._freq[dataset]

    async def liftover_variant(
        self, source_variant_id: str, reference_genome: str
    ) -> list[dict[str, Any]]:
        return list(self._lift)


_COMPARE_ARGS = {
    "variant_id": "6-26092913-G-A",
    "datasets": ["gnomad_r4", "gnomad_r2_1"],
    "auto_liftover": True,
}


# ---------------------------------------------------------------------------
# get_variant_frequencies
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_variant_frequencies_minimal() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _FreqStub())
    args = {"variant_id": "7-117559590-ATCT-A"}
    compact = _structured(await mcp.call_tool("get_variant_frequencies", args))
    minimal = _structured(
        await mcp.call_tool("get_variant_frequencies", {**args, "response_mode": "minimal"})
    )

    # (1) envelope + global summary block.
    _assert_minimal_envelope(minimal, dropped=["exome", "genome"])
    assert minimal["summary"]["overall_af"] == compact["summary"]["overall_af"]
    assert minimal["summary"]["max_pop"] == compact["summary"]["max_pop"]
    assert minimal["major_consequence"] == compact["major_consequence"]
    # (2) per-population arrays dropped.
    assert "exome" not in minimal
    assert "genome" not in minimal
    # (3) measured reduction.
    assert _bytes(minimal) < _bytes(compact), (_bytes(minimal), _bytes(compact))
    # (4) compact unchanged: still carries the per-pop exome arrays + summary.
    assert compact["exome"]["populations"]
    assert compact["summary"]["overall_af"] == pytest.approx(0.023, abs=1e-6)


@pytest.mark.asyncio
async def test_variant_frequencies_full_is_most_inclusive() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _FreqStub())
    full = _structured(
        await mcp.call_tool(
            "get_variant_frequencies",
            {"variant_id": "7-117559590-ATCT-A", "response_mode": "full"},
        )
    )
    # full keeps the zero-AC afr row that compact would also keep here; the key
    # guarantee is that the per-population breakdown survives in full mode.
    assert full["exome"]["populations"]
    assert {p["id"] for p in full["exome"]["populations"]} >= {"nfe", "afr"}


# ---------------------------------------------------------------------------
# compute_carrier_frequency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_carrier_frequency_minimal() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _FreqStub())
    args = {"variant_id": "7-117559590-ATCT-A", "inheritance": "AR"}
    compact = _structured(await mcp.call_tool("compute_carrier_frequency", args))
    minimal = _structured(
        await mcp.call_tool("compute_carrier_frequency", {**args, "response_mode": "minimal"})
    )

    _assert_minimal_envelope(minimal, dropped=["per_population", "citations"])
    # global overall block preserved verbatim + inheritance.
    assert minimal["overall"] == compact["overall"]
    assert minimal["inheritance"] == "AR"
    # citations_ref kept (groundable) but the full citation list / per-pop dropped.
    assert minimal["citations_ref"] == "gnomad://citations"
    assert "per_population" not in minimal
    assert "citations" not in minimal
    assert _bytes(minimal) < _bytes(compact)
    # compact unchanged: per-population rows + citations list present.
    assert compact["per_population"]
    assert isinstance(compact["citations"], list) and compact["citations"]


@pytest.mark.asyncio
async def test_carrier_frequency_full_unchanged() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _FreqStub())
    full = _structured(
        await mcp.call_tool(
            "compute_carrier_frequency",
            {"variant_id": "7-117559590-ATCT-A", "inheritance": "AR", "response_mode": "full"},
        )
    )
    # full inlines the complete bibliographic citations (longer than the short forms).
    assert any("doi" in c or "Nature" in c for c in full["citations"]), full["citations"]
    assert full["per_population"]


# ---------------------------------------------------------------------------
# compute_gene_carrier_frequency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gene_carrier_frequency_minimal() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _GeneCarrierStub())
    args = {"gene_symbol": "CFTR"}
    compact = _structured(await mcp.call_tool("compute_gene_carrier_frequency", args))
    minimal = _structured(
        await mcp.call_tool("compute_gene_carrier_frequency", {**args, "response_mode": "minimal"})
    )

    _assert_minimal_envelope(minimal, dropped=["populations", "contributing_variants.top"])
    # global block preserved + contributing COUNT only.
    assert minimal["global"] == compact["global"]
    assert minimal["contributing_variants"] == {"count": 523}
    assert "top" not in minimal["contributing_variants"]
    assert "populations" not in minimal
    assert _bytes(minimal) < _bytes(compact)
    # compact unchanged: per-population rows + contributing list present.
    assert compact["populations"]
    assert "top" in compact["contributing_variants"]


@pytest.mark.asyncio
async def test_gene_carrier_frequency_full_unchanged() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _GeneCarrierStub())
    full = _structured(
        await mcp.call_tool(
            "compute_gene_carrier_frequency", {"gene_symbol": "CFTR", "response_mode": "full"}
        )
    )
    # full returns the complete contributing-variant list (2 in the canned data).
    assert full["contributing_variants"]["top"]
    assert full["populations"]


# ---------------------------------------------------------------------------
# get_gene_details
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gene_details_minimal() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _GeneStub())
    args = {"gene_symbol": "PCSK9"}
    compact = _structured(await mcp.call_tool("get_gene_details", args))
    minimal = _structured(
        await mcp.call_tool("get_gene_details", {**args, "response_mode": "minimal"})
    )

    _assert_minimal_envelope(minimal, dropped=["gnomad_constraint(full matrix)"])
    # symbol/gene_id + pLI/oe_lof + coordinates preserved.
    assert minimal["symbol"] == "PCSK9"
    assert minimal["gene_id"] == "ENSG00000169174"
    assert minimal["gnomad_constraint"] == {"pli": 0.0042, "oe_lof": 0.83}
    assert minimal["chrom"] == "1"
    assert minimal["start"] == 55039447 and minimal["stop"] == 55064852
    # heavy arrays absent (already dropped in compact too).
    assert "transcripts" not in minimal
    assert "exons" not in minimal
    assert _bytes(minimal) < _bytes(compact)
    # compact unchanged: full constraint matrix present (more than pli/oe_lof).
    assert set(compact["gnomad_constraint"]) > {"pli", "oe_lof"}


@pytest.mark.asyncio
async def test_gene_details_full_unchanged() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _GeneStub())
    full = _structured(
        await mcp.call_tool("get_gene_details", {"gene_symbol": "PCSK9", "response_mode": "full"})
    )
    # full passes through the heavy arrays.
    assert full["transcripts"]
    assert full["exons"]


# ---------------------------------------------------------------------------
# get_gene_summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gene_summary_minimal() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _GeneSummaryStub())
    args = {"gene_symbol": "PCSK9"}
    compact = _structured(await mcp.call_tool("get_gene_summary", args))
    minimal = _structured(
        await mcp.call_tool("get_gene_summary", {**args, "response_mode": "minimal"})
    )

    _assert_minimal_envelope(minimal, dropped=["clinvar_summary.top_pathogenic", "expression"])
    # top-line constraint + pathogenic COUNT preserved.
    assert minimal["constraint"] == {"pli": 0.01, "oe_lof": 0.8}
    assert minimal["clinvar_summary"] == {"pathogenic_count": 2}
    assert "top_pathogenic" not in minimal["clinvar_summary"]
    assert "expression" not in minimal
    assert _bytes(minimal) < _bytes(compact)
    # compact unchanged: ranked pathogenic rows + expression present.
    assert compact["clinvar_summary"]["top_pathogenic"]
    assert compact["expression"]["mean_pext"] == 0.7


@pytest.mark.asyncio
async def test_gene_summary_full_unchanged() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _GeneSummaryStub())
    full = _structured(
        await mcp.call_tool("get_gene_summary", {"gene_symbol": "PCSK9", "response_mode": "full"})
    )
    # full returns the raw clinvar_variants list (not the ranked summary).
    assert isinstance(full["clinvar_variants"], list) and len(full["clinvar_variants"]) == 3
    assert "clinvar_summary" not in full


# ---------------------------------------------------------------------------
# compare_variant_across_datasets
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compare_variant_minimal() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _CompareStub())
    compact = _structured(await mcp.call_tool("compare_variant_across_datasets", _COMPARE_ARGS))
    minimal = _structured(
        await mcp.call_tool(
            "compare_variant_across_datasets", {**_COMPARE_ARGS, "response_mode": "minimal"}
        )
    )

    _assert_minimal_envelope(
        minimal, dropped=["comparison.per_population_af_deltas"], expects_headline=True
    )
    # per-dataset present flags + global AF per dataset preserved.
    assert minimal["datasets"]["gnomad_r4"]["present"] is True
    assert minimal["datasets"]["gnomad_r2_1"]["present"] is True
    assert minimal["datasets"]["gnomad_r2_1"]["lifted_variant_id"] == "6-26093141-G-A"
    assert (
        minimal["comparison"]["overall_af_by_dataset"]
        == (compact["comparison"]["overall_af_by_dataset"])
    )
    # raw per-dataset rows + per_population_af_deltas dropped.
    assert "exome" not in minimal["datasets"]["gnomad_r4"]
    assert "summary" not in minimal["datasets"]["gnomad_r4"]
    assert "per_population_af_deltas" not in minimal["comparison"]
    assert _bytes(minimal) < _bytes(compact)
    # compact unchanged: per_population_af_deltas + per-dataset summary present.
    assert compact["comparison"]["per_population_af_deltas"]
    assert "summary" in compact["datasets"]["gnomad_r4"]


@pytest.mark.asyncio
async def test_compare_variant_full_unchanged() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _CompareStub())
    full = _structured(
        await mcp.call_tool(
            "compare_variant_across_datasets", {**_COMPARE_ARGS, "response_mode": "full"}
        )
    )
    # full keeps the raw per-dataset population rows.
    assert full["datasets"]["gnomad_r4"]["exome"]["populations"]
    assert "populations_note" not in full
