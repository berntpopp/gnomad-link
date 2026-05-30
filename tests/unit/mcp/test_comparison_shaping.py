"""Unit tests for comparison_shaping: aligning per-dataset frequency shapes.

Task C2.1 of the new-tools plan. compare_variant_across_datasets fans out
get_variant_frequencies per dataset, reuses shape_variant_frequencies per
dataset, then this module aligns the per-population AF rows across datasets and
computes deltas. Pure functions over already-shaped dicts; no service calls.
"""

from __future__ import annotations

from typing import Any


def _shaped(
    *,
    variant_id: str,
    dataset: str,
    overall_af: float,
    pops: dict[str, float],
) -> dict[str, Any]:
    """Build a minimal shape_variant_frequencies-style dict for one dataset."""
    return {
        "variant_id": variant_id,
        "dataset": dataset,
        "gene_symbol": "PCSK9",
        "major_consequence": "missense_variant",
        "exome": {
            "ac": 10,
            "an": 100_000,
            "af": overall_af,
            "homozygote_count": 0,
            "hemizygote_count": None,
            "populations": [
                {"id": pid, "ac": 1, "an": 1_000, "af": af, "homozygote_count": 0}
                for pid, af in pops.items()
            ],
        },
        "genome": None,
        "summary": {"overall_af": overall_af, "has_clinvar": None},
    }


def test_aligns_overall_af_by_dataset_for_present_datasets() -> None:
    from gnomad_link.mcp.comparison_shaping import build_comparison

    per_dataset = {
        "gnomad_r4": {
            "present": True,
            **_shaped(
                variant_id="1-55039974-G-T",
                dataset="gnomad_r4",
                overall_af=0.002,
                pops={"afr": 0.01, "nfe": 0.001},
            ),
        },
        "gnomad_r3": {
            "present": True,
            **_shaped(
                variant_id="1-55039974-G-T",
                dataset="gnomad_r3",
                overall_af=0.0018,
                pops={"afr": 0.009, "nfe": 0.0012},
            ),
        },
        "gnomad_r2_1": {"present": False},
    }

    comparison = build_comparison(per_dataset)

    assert comparison["overall_af_by_dataset"] == {
        "gnomad_r4": 0.002,
        "gnomad_r3": 0.0018,
    }
    assert "gnomad_r2_1" not in comparison["overall_af_by_dataset"]


def test_per_population_deltas_use_max_minus_min_across_present_datasets() -> None:
    from gnomad_link.mcp.comparison_shaping import build_comparison

    per_dataset = {
        "gnomad_r4": {
            "present": True,
            **_shaped(
                variant_id="1-55039974-G-T",
                dataset="gnomad_r4",
                overall_af=0.002,
                pops={"afr": 0.01, "nfe": 0.001},
            ),
        },
        "gnomad_r3": {
            "present": True,
            **_shaped(
                variant_id="1-55039974-G-T",
                dataset="gnomad_r3",
                overall_af=0.0018,
                pops={"afr": 0.009, "nfe": 0.0012},
            ),
        },
    }

    comparison = build_comparison(per_dataset)
    by_pop = {row["population"]: row for row in comparison["per_population_af_deltas"]}

    assert by_pop["afr"]["af_by_dataset"] == {"gnomad_r4": 0.01, "gnomad_r3": 0.009}
    assert abs(by_pop["afr"]["max_minus_min_delta"] - 0.001) < 1e-12
    assert abs(by_pop["nfe"]["max_minus_min_delta"] - 0.0002) < 1e-12


def test_population_present_in_only_one_dataset_has_zero_delta() -> None:
    from gnomad_link.mcp.comparison_shaping import build_comparison

    per_dataset = {
        "gnomad_r4": {
            "present": True,
            **_shaped(
                variant_id="1-1-A-T",
                dataset="gnomad_r4",
                overall_af=0.002,
                pops={"afr": 0.01, "mid": 0.05},
            ),
        },
        "gnomad_r3": {
            "present": True,
            **_shaped(
                variant_id="1-1-A-T",
                dataset="gnomad_r3",
                overall_af=0.0018,
                pops={"afr": 0.009},
            ),
        },
    }

    comparison = build_comparison(per_dataset)
    by_pop = {row["population"]: row for row in comparison["per_population_af_deltas"]}

    # mid only exists in r4: single value, delta is 0.0.
    assert by_pop["mid"]["af_by_dataset"] == {"gnomad_r4": 0.05}
    assert by_pop["mid"]["max_minus_min_delta"] == 0.0


def test_deltas_sorted_by_largest_delta_first() -> None:
    from gnomad_link.mcp.comparison_shaping import build_comparison

    per_dataset = {
        "gnomad_r4": {
            "present": True,
            **_shaped(
                variant_id="1-1-A-T",
                dataset="gnomad_r4",
                overall_af=0.5,
                pops={"afr": 0.5, "nfe": 0.10},
            ),
        },
        "gnomad_r3": {
            "present": True,
            **_shaped(
                variant_id="1-1-A-T",
                dataset="gnomad_r3",
                overall_af=0.1,
                pops={"afr": 0.1, "nfe": 0.09},
            ),
        },
    }

    comparison = build_comparison(per_dataset)
    deltas = comparison["per_population_af_deltas"]

    # afr swing (0.4) must sort before nfe swing (0.01).
    assert [row["population"] for row in deltas] == ["afr", "nfe"]


def test_genome_only_dataset_populations_are_aligned() -> None:
    from gnomad_link.mcp.comparison_shaping import build_comparison

    r3 = _shaped(
        variant_id="1-1-A-T",
        dataset="gnomad_r3",
        overall_af=0.02,
        pops={"afr": 0.02},
    )
    # Move the populations to the genome block; r3 is whole-genome.
    r3["genome"] = r3.pop("exome")
    r3["exome"] = None

    per_dataset = {
        "gnomad_r4": {
            "present": True,
            **_shaped(
                variant_id="1-1-A-T",
                dataset="gnomad_r4",
                overall_af=0.03,
                pops={"afr": 0.03},
            ),
        },
        "gnomad_r3": {"present": True, **r3},
    }

    comparison = build_comparison(per_dataset)
    by_pop = {row["population"]: row for row in comparison["per_population_af_deltas"]}

    assert by_pop["afr"]["af_by_dataset"] == {"gnomad_r4": 0.03, "gnomad_r3": 0.02}
    assert abs(by_pop["afr"]["max_minus_min_delta"] - 0.01) < 1e-12


def test_no_present_datasets_yields_empty_comparison() -> None:
    from gnomad_link.mcp.comparison_shaping import build_comparison

    comparison = build_comparison(
        {"gnomad_r4": {"present": False}, "gnomad_r3": {"present": False}}
    )

    assert comparison["overall_af_by_dataset"] == {}
    assert comparison["per_population_af_deltas"] == []
