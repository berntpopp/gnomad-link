"""Pure Hardy-Weinberg carrier/affected-frequency math for compute_carrier_frequency.

No I/O, no gnomAD, no MCP. Every function is closed-form and golden-tested.

References:
- Schrodi et al. 2015, Hum Genet, doi:10.1007/s00439-015-1551-8 (2pq / q^2 carrier
  framework and confidence-interval concept).
- Karczewski et al. 2020 (gnomAD allele-frequency reference).
- Guo et al. 2019; Zhu et al. 2022 (homozygote-corrected variant carrier rate).
- Hotakainen et al. 2025; Kandolin et al. 2024 (X-linked sex-split estimation).

All estimates assume Hardy-Weinberg equilibrium, random mating, complete
penetrance, a single causal variant, and represent a minimum estimate.
"""

from __future__ import annotations

import math

# Standard normal quantile for a two-sided 95% interval.
_WILSON_Z = 1.96


def ar_carrier(q: float) -> float:
    """Autosomal-recessive carrier frequency under HWE: 2*p*q (p = 1 - q)."""
    p = 1.0 - q
    return 2.0 * p * q


def ar_affected(q: float) -> float:
    """Autosomal-recessive affected frequency under HWE: q**2."""
    return q * q


def variant_carrier_rate(*, ac: int, homozygote_count: int, an: int) -> float | None:
    """Homozygote-corrected variant carrier rate: (ac - 2*hom) / (an / 2).

    Returns None when an == 0 (carrier frequency is undefined, not zero).
    """
    if an <= 0:
        return None
    return (ac - 2 * homozygote_count) / (an / 2.0)


def ad_affected_or_carrier(q: float) -> float:
    """Autosomal-dominant affected-or-carrier frequency: 1 - (1 - q)**2.

    Algebraically equal to 2q - q**2 (Whiffin et al. 2017).
    """
    return 1.0 - (1.0 - q) ** 2


def xl_female_carrier(q_xx: float) -> float:
    """X-linked heterozygous female carrier frequency: 2*q_XX (HWE)."""
    return 2.0 * q_xx


def xl_affected_female(q_xx: float) -> float:
    """X-linked homozygous affected female frequency: q_XX**2 (HWE)."""
    return q_xx * q_xx


def xl_affected_male(q_xy: float) -> float:
    """X-linked affected male frequency: hemizygous AF (no 2x, no square)."""
    return q_xy


def wilson_ci(*, af: float, n: int) -> tuple[float | None, float | None]:
    """Closed-form Wilson 95% score interval for a binomial proportion.

    af is the point estimate (k/n); n is the allele number. Returns (low, high)
    clamped to [0, 1]. Returns (None, None) when n <= 0 so callers do not emit a
    spurious zero-width interval.
    """
    if n <= 0:
        return (None, None)
    z = _WILSON_Z
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (af + z2 / (2.0 * n)) / denom
    half = (z / denom) * math.sqrt(af * (1.0 - af) / n + z2 / (4.0 * n * n))
    low = max(0.0, center - half)
    high = min(1.0, center + half)
    return (low, high)
