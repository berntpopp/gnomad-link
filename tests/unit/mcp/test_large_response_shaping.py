from __future__ import annotations

import pytest

from gnomad_link.mcp.shaping import cap_region_span, shape_gene_variants


def _gen_variants(n: int) -> list[dict]:
    return [
        {
            "variant_id": f"1-{i}-A-T",
            "af": (i % 10) / 10000,
            "ac": i,
            "major_consequence": "missense_variant",
        }
        for i in range(1, n + 1)
    ]


def test_gene_variants_limit_truncates() -> None:
    payload = shape_gene_variants(
        _gen_variants(250), limit=50, consequence=None, max_af=None, min_ac=None
    )
    assert payload["returned"] == 50
    assert payload["truncated"]["kind"] == "gene_variants"


def test_gene_variants_max_af_filter() -> None:
    payload = shape_gene_variants(
        _gen_variants(50), limit=100, consequence=None, max_af=0.0001, min_ac=None
    )
    assert all(v["af"] <= 0.0001 for v in payload["variants"])


def test_gene_variants_invalid_limit() -> None:
    with pytest.raises(ValueError):
        shape_gene_variants([], limit=0, consequence=None, max_af=None, min_ac=None)
    with pytest.raises(ValueError):
        shape_gene_variants([], limit=600, consequence=None, max_af=None, min_ac=None)


def test_cap_region_span_no_change_when_in_bounds() -> None:
    start, stop, capped = cap_region_span("1", 100, 1000)
    assert (start, stop, capped) == (100, 1000, False)


def test_cap_region_span_clamps() -> None:
    start, stop, capped = cap_region_span("1", 100, 1_000_000)
    assert capped is True
    assert stop - start == 100_000


def test_truncated_block_includes_to_restore_for_consequence() -> None:
    # All 10 variants have consequence=missense_variant, so no by_consequence drops.
    # Change to a different consequence to force drops.
    payload2 = shape_gene_variants(
        _gen_variants(10),
        limit=100,
        consequence="stop_gained",
        max_af=None,
        min_ac=None,
    )
    # All 10 dropped by_consequence since none match stop_gained.
    trunc = payload2.get("truncated")
    assert trunc is not None
    assert trunc["dropped"]["by_consequence"] == 10
    assert "to_restore" in trunc
    assert "consequence" in trunc["to_restore"]


def test_truncated_block_includes_to_restore_for_max_af() -> None:
    # With max_af=0 all variants get dropped by max_af filter.
    payload = shape_gene_variants(
        _gen_variants(10), limit=100, consequence=None, max_af=0.0, min_ac=None
    )
    trunc = payload.get("truncated")
    assert trunc is not None
    assert "to_restore" in trunc
    assert "max_af" in trunc["to_restore"]
