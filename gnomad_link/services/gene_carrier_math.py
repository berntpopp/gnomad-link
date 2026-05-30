"""Pure gene-level carrier-frequency aggregation math.

Ports the gnomad-carrier-frequency algorithm: sum qualifying pathogenic variants
per population, then derive carrier frequency by one of three methods. No I/O.

- hom_exclusion (default): Gene Carrier Rate GCR = 1 - prod(1 - VCR_i), where the
  per-variant carrier rate VCR_i = (ac - 2*hom) / (an/2) (Karczewski 2022 Eq. 1-3).
- hwe: 2*p*q with q = sum(ac/an) over variants (Hardy-Weinberg 2pq).
- simplified: 2 * sum(ac/an).

Genetic prevalence is always q^2 (q = sum_af); Bayesian prevalence is q^2 * penetrance.

References: Karczewski et al. 2022 (PMC9763236); Schrodi et al. 2015
(doi:10.1007/s00439-015-1551-8); Karczewski et al. 2020 (gnomAD).
"""

from __future__ import annotations

from collections.abc import Sequence

from gnomad_link.services.carrier_math import ar_carrier, variant_carrier_rate


def gene_carrier_rate(vcrs: Sequence[float]) -> float:
    """Inclusion-exclusion gene carrier rate: 1 - prod(1 - VCR_i)."""
    product = 1.0
    for vcr in vcrs:
        product *= 1.0 - vcr
    return 1.0 - product


def simplified_carrier(sum_af: float) -> float:
    """Simplified carrier frequency: 2 * sum(allele frequencies)."""
    return 2.0 * sum_af


def hwe_expected_homozygotes(af: float, individuals: float) -> float:
    """Expected homozygote count under HWE: af^2 * N (N = allele_number / 2)."""
    return af * af * individuals


def aggregate_carrier(
    rows: Sequence[tuple[int, int, int]],
    *,
    method: str = "hom_exclusion",
    penetrance: float = 1.0,
) -> dict[str, float | int | str]:
    """Aggregate per-variant (ac, an, homozygote_count) into carrier metrics.

    ``rows`` are the per-variant counts for ONE population (or global) over the
    already-qualifying variants. Variants with an == 0 are skipped (undefined AF).
    """
    sum_af = 0.0
    total_ac = 0
    max_an = 0
    vcrs: list[float] = []
    for ac, an, hom in rows:
        total_ac += ac
        if an > max_an:
            max_an = an
        if an <= 0:
            continue
        sum_af += ac / an
        vcr = variant_carrier_rate(ac=ac, homozygote_count=hom, an=an)
        if vcr is not None:
            vcrs.append(vcr)

    if method == "hom_exclusion":
        carrier = gene_carrier_rate(vcrs)
    elif method == "hwe":
        carrier = ar_carrier(sum_af)
    else:  # simplified
        carrier = simplified_carrier(sum_af)

    genetic_prevalence = sum_af * sum_af
    return {
        "carrier_frequency": carrier,
        "sum_af": sum_af,
        "total_ac": total_ac,
        "max_an": max_an,
        "genetic_prevalence": genetic_prevalence,
        "bayesian_prevalence": genetic_prevalence * penetrance,
        "method": method,
    }
