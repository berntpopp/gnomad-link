from __future__ import annotations

import pytest

from gnomad_link.services.gene_carrier_math import (
    aggregate_carrier,
    gene_carrier_rate,
    hwe_expected_homozygotes,
    simplified_carrier,
)


def test_gene_carrier_rate_single_variant() -> None:
    # VCR 0.02 -> GCR = 1 - (1-0.02) = 0.02
    assert gene_carrier_rate([0.02]) == pytest.approx(0.02, abs=1e-12)


def test_gene_carrier_rate_inclusion_exclusion_two_variants() -> None:
    # 1 - (1-0.02)(1-0.008) = 0.02784
    assert gene_carrier_rate([0.02, 0.008]) == pytest.approx(0.02784, abs=1e-9)


def test_gene_carrier_rate_empty_is_zero() -> None:
    assert gene_carrier_rate([]) == 0.0


def test_simplified_carrier_is_two_sum_af() -> None:
    assert simplified_carrier(0.015) == pytest.approx(0.03, abs=1e-12)


def test_hwe_expected_homozygotes() -> None:
    # af=0.01, individuals=5000 -> 0.0001 * 5000 = 0.5
    assert hwe_expected_homozygotes(0.01, 5000) == pytest.approx(0.5, abs=1e-12)


def test_aggregate_hom_exclusion_default_two_variants() -> None:
    rows = [(100, 10000, 0), (50, 10000, 5)]  # (ac, an, hom)
    out = aggregate_carrier(rows, method="hom_exclusion", penetrance=1.0)
    assert out["sum_af"] == pytest.approx(0.015, abs=1e-12)
    assert out["total_ac"] == 150
    assert out["max_an"] == 10000
    assert out["carrier_frequency"] == pytest.approx(0.02784, abs=1e-9)
    assert out["genetic_prevalence"] == pytest.approx(0.000225, abs=1e-12)
    assert out["bayesian_prevalence"] == pytest.approx(0.000225, abs=1e-12)
    assert out["method"] == "hom_exclusion"


def test_aggregate_hwe_formula() -> None:
    rows = [(100, 10000, 0), (50, 10000, 5)]
    out = aggregate_carrier(rows, method="hwe", penetrance=1.0)
    # 2 * (1 - 0.015) * 0.015 = 0.02955
    assert out["carrier_frequency"] == pytest.approx(0.02955, abs=1e-9)


def test_aggregate_simplified_formula() -> None:
    rows = [(100, 10000, 0), (50, 10000, 5)]
    out = aggregate_carrier(rows, method="simplified", penetrance=1.0)
    assert out["carrier_frequency"] == pytest.approx(0.03, abs=1e-12)


def test_aggregate_penetrance_scales_bayesian_only() -> None:
    rows = [(100, 10000, 0)]
    out = aggregate_carrier(rows, method="hwe", penetrance=0.5)
    assert out["genetic_prevalence"] == pytest.approx(0.0001, abs=1e-12)
    assert out["bayesian_prevalence"] == pytest.approx(0.00005, abs=1e-12)


def test_aggregate_zero_an_variant_skipped() -> None:
    rows = [(0, 0, 0), (100, 10000, 0)]
    out = aggregate_carrier(rows, method="hom_exclusion", penetrance=1.0)
    assert out["sum_af"] == pytest.approx(0.01, abs=1e-12)
    assert out["carrier_frequency"] == pytest.approx(0.02, abs=1e-9)


def test_aggregate_empty_rows() -> None:
    out = aggregate_carrier([], method="hom_exclusion", penetrance=1.0)
    assert out["sum_af"] == 0.0
    assert out["carrier_frequency"] == 0.0
    assert out["max_an"] == 0
