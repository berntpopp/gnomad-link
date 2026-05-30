from __future__ import annotations

from gnomad_link.mcp.gene_summary_shaping import compact_expression, rank_pathogenic_clinvar


def test_rank_pathogenic_keeps_only_p_lp_sorted_by_gold_stars() -> None:
    rows = [
        {"variant_id": "1-1-A-G", "clinical_significance": "Benign", "gold_stars": 4},
        {"variant_id": "1-2-A-G", "clinical_significance": "Likely pathogenic", "gold_stars": 1},
        {"variant_id": "1-3-A-G", "clinical_significance": "Pathogenic", "gold_stars": 3},
        {
            "variant_id": "1-4-A-G",
            "clinical_significance": "Uncertain significance",
            "gold_stars": 2,
        },
        {
            "variant_id": "1-5-A-G",
            "clinical_significance": "Pathogenic/Likely pathogenic",
            "gold_stars": 2,
        },
    ]

    summary = rank_pathogenic_clinvar(rows, clinvar_limit=10)

    assert summary["pathogenic_count"] == 3
    # Highest gold_stars first; only P / LP rows survive.
    assert [r["variant_id"] for r in summary["top_pathogenic"]] == [
        "1-3-A-G",
        "1-5-A-G",
        "1-2-A-G",
    ]
    # Compact rows expose only the four advertised keys.
    assert set(summary["top_pathogenic"][0]) == {
        "variant_id",
        "clinical_significance",
        "gold_stars",
        "major_consequence",
    }
    assert "truncated" not in summary


def test_rank_pathogenic_emits_truncated_when_capped() -> None:
    rows = [
        {"variant_id": f"1-{i}-A-G", "clinical_significance": "Pathogenic", "gold_stars": i}
        for i in range(20)
    ]

    summary = rank_pathogenic_clinvar(rows, clinvar_limit=5)

    assert summary["pathogenic_count"] == 20
    assert len(summary["top_pathogenic"]) == 5
    # Top of the list is the highest gold_stars (19).
    assert summary["top_pathogenic"][0]["variant_id"] == "1-19-A-G"
    assert summary["truncated"] == {
        "kind": "pathogenic_clinvar",
        "dropped": 15,
        "filter": {"clinvar_limit": 5},
        "to_disable": "raise clinvar_limit (max 50) or response_mode='full'",
        "to_restore": "response_mode='full'",
    }


def test_rank_pathogenic_handles_missing_gold_stars() -> None:
    rows = [
        {"variant_id": "1-1-A-G", "clinical_significance": "Pathogenic", "gold_stars": None},
        {"variant_id": "1-2-A-G", "clinical_significance": "Pathogenic", "gold_stars": 1},
    ]

    summary = rank_pathogenic_clinvar(rows, clinvar_limit=10)

    # gold_stars=None ranks below an explicit star count.
    assert [r["variant_id"] for r in summary["top_pathogenic"]] == ["1-2-A-G", "1-1-A-G"]


def test_compact_expression_returns_mean_pext_and_top_tissues() -> None:
    pext = {
        "flags": [],
        "regions": [
            {"start": 1, "stop": 10, "mean": 0.8},
            {"start": 11, "stop": 20, "mean": 0.6},
        ],
    }
    gtex = [
        {"tissue": "Liver", "value": 50.0},
        {"tissue": "Brain", "value": 5.0},
        {"tissue": "Heart", "value": 30.0},
        {"tissue": "Lung", "value": 20.0},
        {"tissue": "Kidney", "value": 40.0},
        {"tissue": "Skin", "value": 1.0},
    ]

    expr = compact_expression(pext=pext, gtex_tissue_expression=gtex, source_build="GRCh38")

    assert expr["source_build"] == "GRCh38"
    assert expr["mean_pext"] == 0.7  # (0.8 + 0.6) / 2
    # Top 5 tissues by value, descending.
    assert [t["tissue"] for t in expr["top_tissues"]] == [
        "Liver",
        "Kidney",
        "Heart",
        "Lung",
        "Brain",
    ]
    assert "unavailable" not in expr


def test_compact_expression_unavailable_when_empty() -> None:
    expr = compact_expression(pext={"flags": [], "regions": []}, gtex_tissue_expression=[])

    assert expr["unavailable"] is True
    assert "empty" in expr["note"]
