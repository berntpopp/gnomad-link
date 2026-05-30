"""Unit tests for SV search shaping (filter + cap + truncated + compact rows).

Mirrors the shape_gene_variants truncation contract: total_seen counts the
FULL upstream list (before the cap), the truncated block reports dropped
counts and a to_restore/to_disable hint, and compact rows are projected to a
fixed keep-set.
"""

from __future__ import annotations

from gnomad_link.mcp.sv_shaping import shape_sv_search

_ROWS = [
    {
        "variant_id": "DEL_19_1",
        "type": "DEL",
        "chrom": "19",
        "pos": 11_089_000,
        "end": 11_133_820,
        "length": 44_820,
        "af": 0.0001,
        "ac": 3,
        "an": 30000,
        "major_consequence": "lof",
        "consequences": [{"consequence": "lof", "genes": ["SMARCA4"]}],
    },
    {
        "variant_id": "DUP_19_2",
        "type": "DUP",
        "chrom": "19",
        "pos": 11_100_000,
        "end": 11_200_000,
        "length": 100_000,
        "af": 0.002,
        "ac": 60,
        "an": 30000,
        "major_consequence": "copy_gain",
    },
    {
        "variant_id": "DEL_19_3",
        "type": "DEL",
        "chrom": "19",
        "pos": 11_300_000,
        "end": 11_300_500,
        "length": 500,
        "af": 0.01,
        "ac": 300,
        "an": 30000,
        "major_consequence": "lof",
    },
]


def test_no_filters_returns_all_with_compact_rows() -> None:
    out = shape_sv_search(_ROWS, sv_type=None, min_length=None, max_length=None, limit=100)

    assert out["returned"] == 3
    assert out["total_seen"] == 3
    assert "truncated" not in out
    # Compact rows keep only the advertised key-set.
    first = out["structural_variants"][0]
    assert set(first) == {
        "variant_id",
        "type",
        "chrom",
        "pos",
        "end",
        "length",
        "af",
        "ac",
        "an",
        "major_consequence",
    }
    assert "consequences" not in first


def test_filter_by_sv_type() -> None:
    out = shape_sv_search(_ROWS, sv_type="DEL", min_length=None, max_length=None, limit=100)

    assert [r["variant_id"] for r in out["structural_variants"]] == ["DEL_19_1", "DEL_19_3"]
    assert out["returned"] == 2
    assert out["total_seen"] == 3
    assert out["truncated"]["kind"] == "structural_variants"
    assert out["truncated"]["dropped"] == 1
    assert out["truncated"]["filter"] == {
        "sv_type": "DEL",
        "min_length": None,
        "max_length": None,
    }


def test_filter_by_length_window() -> None:
    out = shape_sv_search(_ROWS, sv_type=None, min_length=1000, max_length=50_000, limit=100)

    # Only DEL_19_1 (44820) is in [1000, 50000].
    assert [r["variant_id"] for r in out["structural_variants"]] == ["DEL_19_1"]
    assert out["returned"] == 1
    assert out["total_seen"] == 3
    assert out["truncated"]["dropped"] == 2


def test_cap_to_limit_emits_truncated() -> None:
    out = shape_sv_search(_ROWS, sv_type=None, min_length=None, max_length=None, limit=2)

    assert out["returned"] == 2
    assert out["total_seen"] == 3
    assert out["truncated"]["kind"] == "structural_variants"
    assert out["truncated"]["dropped"] == 1
    assert out["truncated"]["to_restore"] == "limit=3"
    assert "to_disable" in out["truncated"]


def test_empty_input_returns_zero_no_truncated() -> None:
    out = shape_sv_search([], sv_type=None, min_length=None, max_length=None, limit=100)

    assert out["returned"] == 0
    assert out["total_seen"] == 0
    assert out["structural_variants"] == []
    assert "truncated" not in out
