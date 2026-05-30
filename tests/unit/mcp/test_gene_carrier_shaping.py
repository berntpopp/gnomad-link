from __future__ import annotations

from typing import Any

from gnomad_link.mcp.gene_carrier_shaping import shape_gene_carrier


def _service_result() -> dict[str, Any]:
    def metrics(cf: float, sum_af: float) -> dict[str, Any]:
        return {
            "carrier_frequency": cf,
            "sum_af": sum_af,
            "total_ac": 100,
            "max_an": 10000,
            "genetic_prevalence": sum_af * sum_af,
            "bayesian_prevalence": sum_af * sum_af,
            "method": "hom_exclusion",
        }

    return {
        "gene": {"gene_id": "ENSG1", "symbol": "CFTR"},
        "dataset": "gnomad_r4",
        "reference_genome": "GRCh38",
        "settings": {"method": "hom_exclusion", "penetrance": 1.0},
        "global": metrics(0.0568, 0.029157),
        "populations": {
            "afr": metrics(0.0228, 0.01127),
            "nfe": metrics(0.0631, 0.031837),
            "asj": metrics(0.1106, 0.055357),
        },
        "qualifying_variants": [
            {"variant_id": f"7-{i}-A-T", "global_af": i / 1000, "source": "plof_only", "flags": []}
            for i in range(1, 6)
        ],
        "qualifying_count": 5,
        "sources": {"plof_only": 5, "clinvar_only": 0, "both": 0},
    }


def test_populations_sorted_by_carrier_desc_with_one_in() -> None:
    shaped = shape_gene_carrier(_service_result(), response_mode="compact", top_variants_limit=10)
    pops = shaped["populations"]
    assert [p["population"] for p in pops] == ["asj", "nfe", "afr"]
    assert pops[0]["carrier_one_in"] == 9  # 1/0.1106
    assert shaped["global"]["carrier_one_in"] == 18  # 1/0.0568
    assert shaped["settings"]["omitted_populations"] == ["sex_split", "subcohort"]


def test_contributing_variants_capped_with_truncated() -> None:
    shaped = shape_gene_carrier(_service_result(), response_mode="compact", top_variants_limit=3)
    cv = shaped["contributing_variants"]
    assert cv["count"] == 5
    assert len(cv["top"]) == 3
    # sorted by global_af desc -> highest first
    assert cv["top"][0]["variant_id"] == "7-5-A-T"
    assert cv["truncated"]["dropped"] == 2


def test_carries_citations_and_assumptions() -> None:
    shaped = shape_gene_carrier(_service_result(), response_mode="compact", top_variants_limit=10)
    assert "assumptions_note" in shaped
    assert any("Schrodi" in c or "Karczewski" in c for c in shaped["citations"])
    assert shaped["sources"] == {"plof_only": 5, "clinvar_only": 0, "both": 0}


def test_leads_with_headline_and_citations_ref() -> None:
    shaped = shape_gene_carrier(_service_result(), response_mode="compact", top_variants_limit=10)
    # headline is the first key so an LLM reads it before parsing the tree.
    assert next(iter(shaped)) == "headline"
    assert shaped["headline"] == (
        "CFTR (gnomad_r4): carrier frequency 1 in 18 globally; "
        "highest 1 in 9 (asj); 5 qualifying variants. Research use only."
    )
    assert shaped["citations_ref"] == "gnomad://citations"
    # compact citations are short (author-year, no DOI prose).
    assert not any("doi:" in c for c in shaped["citations"])


def test_full_mode_inlines_full_citations() -> None:
    shaped = shape_gene_carrier(_service_result(), response_mode="full", top_variants_limit=10)
    assert shaped["citations_ref"] == "gnomad://citations"
    assert any("PMC9763236" in c for c in shaped["citations"])


def test_full_mode_keeps_all_variants() -> None:
    shaped = shape_gene_carrier(_service_result(), response_mode="full", top_variants_limit=3)
    assert len(shaped["contributing_variants"]["top"]) == 5
    assert "truncated" not in shaped["contributing_variants"]


def test_conflicting_resolution_degraded_block_is_surfaced() -> None:
    result = _service_result()
    result["conflicting_resolution_degraded"] = {
        "kind": "conflicting_resolution_incomplete",
        "dropped": 2,
        "cause": "upstream_backpressure",
        "to_restore": "retry compute_gene_carrier_frequency with include_conflicting_clinvar=True",
    }

    shaped = shape_gene_carrier(result, response_mode="compact", top_variants_limit=10)

    assert shaped["degraded"] == result["conflicting_resolution_degraded"]
