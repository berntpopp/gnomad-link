from __future__ import annotations

from typing import Any

from gnomad_link.mcp.coverage_shaping import shape_coverage_payload

_COMPACT_KEEP = {"pos", "mean", "median", "over_20", "over_30"}


def _bin(pos: int, mean: float, over_20: float) -> dict[str, Any]:
    return {
        "pos": pos,
        "mean": mean,
        "median": mean,
        "over_1": 1.0,
        "over_10": 0.99,
        "over_20": over_20,
        "over_30": over_20 - 0.1,
        "over_100": 0.0,
    }


def test_gene_scope_compact_trims_bins_to_keep_set() -> None:
    raw = {
        "gene": {
            "gene_id": "ENSG00000169174",
            "symbol": "PCSK9",
            "coverage": {
                "exome": [_bin(100, 30.0, 0.99)],
                "genome": [_bin(100, 25.0, 0.9)],
            },
        }
    }

    shaped = shape_coverage_payload(
        raw, scope="gene", dataset="gnomad_r4", response_mode="compact", max_bins=500
    )

    assert shaped["scope"] == "gene"
    assert shaped["identity"] == {"gene_id": "ENSG00000169174", "symbol": "PCSK9"}
    assert shaped["dataset"] == "gnomad_r4"
    exome_bin = shaped["exome"]["bins"][0]
    assert set(exome_bin) == _COMPACT_KEEP
    assert "over_100" not in exome_bin


def test_gene_scope_full_keeps_all_bin_fields() -> None:
    raw = {
        "gene": {
            "gene_id": "ENSG1",
            "symbol": "G",
            "coverage": {"exome": [_bin(100, 30.0, 0.99)], "genome": []},
        }
    }

    shaped = shape_coverage_payload(
        raw, scope="gene", dataset="gnomad_r4", response_mode="full", max_bins=500
    )

    assert "over_100" in shaped["exome"]["bins"][0]


def test_summary_computed_from_full_bins_before_cap() -> None:
    # 4 bins; cap to 2. Summary must reflect all 4.
    exome = [_bin(p, mean=float(p), over_20=1.0 if p <= 2 else 0.0) for p in (1, 2, 3, 4)]
    raw = {
        "gene": {
            "gene_id": "ENSG1",
            "symbol": "G",
            "coverage": {"exome": exome, "genome": []},
        }
    }

    shaped = shape_coverage_payload(
        raw, scope="gene", dataset="gnomad_r4", response_mode="compact", max_bins=2
    )

    summary = shaped["exome"]["summary"]
    assert summary["mean_coverage"] == 2.5  # (1+2+3+4)/4
    assert summary["fraction_over_20"] == 0.5  # 2 of 4 bins over_20 == 1.0
    assert len(shaped["exome"]["bins"]) == 2


def test_bin_cap_emits_self_describing_truncated_block() -> None:
    exome = [_bin(p, 30.0, 0.99) for p in range(10)]
    raw = {
        "gene": {
            "gene_id": "ENSG1",
            "symbol": "G",
            "coverage": {"exome": exome, "genome": []},
        }
    }

    shaped = shape_coverage_payload(
        raw, scope="gene", dataset="gnomad_r4", response_mode="compact", max_bins=4
    )

    trunc = shaped["exome"]["truncated"]
    assert trunc["kind"] == "coverage_bins"
    assert trunc["dropped"] == 6
    assert "max_bins" in trunc["to_disable"]
    assert "max_bins" in trunc["to_restore"]


def test_no_truncated_block_when_under_cap() -> None:
    raw = {
        "gene": {
            "gene_id": "ENSG1",
            "symbol": "G",
            "coverage": {"exome": [_bin(1, 30.0, 0.99)], "genome": []},
        }
    }

    shaped = shape_coverage_payload(
        raw, scope="gene", dataset="gnomad_r4", response_mode="compact", max_bins=500
    )

    assert "truncated" not in shaped["exome"]


def test_region_scope_identity_is_chrom_start_stop() -> None:
    raw = {
        "region": {
            "chrom": "1",
            "start": 100,
            "stop": 200,
            "coverage": {"exome": [_bin(100, 30.0, 0.99)], "genome": []},
        }
    }

    shaped = shape_coverage_payload(
        raw, scope="region", dataset="gnomad_r4", response_mode="compact", max_bins=500
    )

    assert shaped["scope"] == "region"
    assert shaped["identity"] == {"chrom": "1", "start": 100, "stop": 200}


def test_variant_scope_is_scalar_no_bins() -> None:
    raw = {
        "variant": {
            "variant_id": "1-55039447-A-G",
            "coverage": {
                "exome": {"mean": 31.0, "median": 31, "over_20": 0.99, "over_30": 0.82},
                "genome": {"mean": 27.0, "median": 27, "over_20": 0.95, "over_30": 0.55},
            },
        }
    }

    shaped = shape_coverage_payload(
        raw, scope="variant", dataset="gnomad_r4", response_mode="compact", max_bins=500
    )

    assert shaped["scope"] == "variant"
    assert shaped["identity"] == {"variant_id": "1-55039447-A-G"}
    assert shaped["exome"] == {"mean": 31.0, "median": 31, "over_20": 0.99, "over_30": 0.82}
    assert "bins" not in shaped["exome"]
    assert shaped["genome"]["mean"] == 27.0
