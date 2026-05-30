from __future__ import annotations

import math

import pytest

from gnomad_link.services.carrier_math import (
    ad_affected_or_carrier,
    ar_affected,
    ar_carrier,
    variant_carrier_rate,
    wilson_ci,
    xl_affected_female,
    xl_affected_male,
    xl_female_carrier,
)


def test_ar_carrier_cftr_like_golden() -> None:
    # CFTR-like q = 0.023 -> 2pq = 0.044942
    assert ar_carrier(0.023) == pytest.approx(0.044942, abs=1e-9)


def test_ar_affected_cftr_like_golden() -> None:
    # q = 0.023 -> q**2 = 0.000529
    assert ar_affected(0.023) == pytest.approx(0.000529, abs=1e-9)


def test_ar_carrier_second_golden() -> None:
    # q = 0.011 -> 2pq = 0.021758
    assert ar_carrier(0.011) == pytest.approx(0.021758, abs=1e-9)


def test_ar_carrier_zero_af_is_zero() -> None:
    assert ar_carrier(0.0) == 0.0
    assert ar_affected(0.0) == 0.0


def test_ad_affected_or_carrier_equals_two_q_minus_q_squared() -> None:
    q = 0.023
    assert ad_affected_or_carrier(q) == pytest.approx(2 * q - q**2, abs=1e-12)
    assert ad_affected_or_carrier(q) == pytest.approx(1 - (1 - q) ** 2, abs=1e-12)


def test_variant_carrier_rate_hom_corrected() -> None:
    # ac=100, hom=10, an=20000 -> (100 - 20) / (20000/2) = 80 / 10000 = 0.008
    assert variant_carrier_rate(ac=100, homozygote_count=10, an=20000) == pytest.approx(
        0.008, abs=1e-12
    )


def test_variant_carrier_rate_zero_an_is_none() -> None:
    assert variant_carrier_rate(ac=0, homozygote_count=0, an=0) is None


def test_xl_female_carrier_uses_two_q() -> None:
    # q_XX = 0.01 -> 2 * 0.01 = 0.02
    assert xl_female_carrier(0.01) == pytest.approx(0.02, abs=1e-12)


def test_xl_affected_female_is_q_squared() -> None:
    assert xl_affected_female(0.01) == pytest.approx(0.0001, abs=1e-12)


def test_xl_affected_male_is_hemizygous_af() -> None:
    # Hemizygous: no 2x, no square; affected male == q_XY.
    assert xl_affected_male(0.01) == pytest.approx(0.01, abs=1e-12)


def test_wilson_ci_known_value() -> None:
    # af = 0.5, n = 100, z = 1.96 -> closed-form center/half.
    low, high = wilson_ci(af=0.5, n=100)
    z = 1.96
    center = (0.5 + z * z / (2 * 100)) / (1 + z * z / 100)
    half = (z / (1 + z * z / 100)) * math.sqrt(0.5 * 0.5 / 100 + z * z / (4 * 100 * 100))
    assert low == pytest.approx(center - half, abs=1e-12)
    assert high == pytest.approx(center + half, abs=1e-12)


def test_wilson_ci_bounds_are_clamped_to_unit_interval() -> None:
    low, high = wilson_ci(af=0.001, n=10)
    assert low >= 0.0
    assert high <= 1.0


def test_wilson_ci_zero_n_is_none() -> None:
    assert wilson_ci(af=0.0, n=0) == (None, None)
