"""Qualifying-variant filter and quality-flag predicates for gene carrier frequency.

Ports the gnomad-carrier-frequency variant-filters decision tree:
- LOFTEE "HC" on the canonical transcript qualifies on its own.
- Missense/inframe qualifies only with ClinVar P/LP evidence (and the missense
  toggle on).
- Any other consequence qualifies only with ClinVar P/LP evidence.
- ClinVar P/LP = significance contains "pathogenic", not "conflicting", and
  gold_stars >= threshold. Conflicting classifications are opt-in and resolved
  by a >= threshold% pathogenic share of individual submissions.

Quality flags (High AF / High Hom / gnomAD-filtered / genomes-only) annotate
variants; hard exclusion on each is opt-in.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from gnomad_link.services.gene_carrier_math import hwe_expected_homozygotes

_MISSENSE_TERMS = {"missense_variant", "inframe_insertion", "inframe_deletion"}

# ClinVar submission significances that do not count toward the conflicting
# pathogenic-share denominator (mirrors the sibling's skip list).
_INVALID_SUBMISSION_SIGS = {
    "not provided",
    "other",
    "risk factor",
    "drug response",
    "association",
    "protective",
    "affects",
    "confers sensitivity",
    "uncertain risk allele",
    "likely risk allele",
    "established risk allele",
}


@dataclass(frozen=True)
class FilterConfig:
    """Qualifying-variant configuration (defaults match gnomad-carrier-frequency)."""

    lof_hc_enabled: bool = True
    missense_enabled: bool = True
    clinvar_enabled: bool = True
    clinvar_star_threshold: int = 2
    include_conflicting: bool = False
    conflicting_threshold: float = 80.0


def is_hc_lof(consequence: dict[str, Any] | None) -> bool:
    """LOFTEE high-confidence LoF on the canonical transcript."""
    if not consequence:
        return False
    return bool(consequence.get("is_canonical")) and consequence.get("lof") == "HC"


def is_missense(consequence: dict[str, Any] | None) -> bool:
    """Missense / inframe indel on the canonical transcript."""
    if not consequence or not consequence.get("is_canonical"):
        return False
    terms = consequence.get("consequence_terms") or []
    return any(term in _MISSENSE_TERMS for term in terms)


def is_conflicting(clinvar: dict[str, Any]) -> bool:
    sig = (clinvar.get("clinical_significance") or "").lower()
    return "conflicting" in sig


def is_pathogenic_clinvar(clinvar: dict[str, Any], star_threshold: int) -> bool:
    """ClinVar Pathogenic/Likely pathogenic, non-conflicting, above the star floor."""
    sig = (clinvar.get("clinical_significance") or "").lower()
    is_pathogenic = "pathogenic" in sig and "conflicting" not in sig
    return is_pathogenic and (clinvar.get("gold_stars") or 0) >= star_threshold


def _submission_is_pathogenic(sig: str) -> bool:
    low = sig.lower()
    return "pathogenic" in low and "conflicting" not in low


def meets_conflicting_threshold(
    submissions: Sequence[dict[str, Any]], threshold_pct: float
) -> bool:
    """True when >= threshold_pct of valid submissions are P/LP."""
    valid = 0
    pathogenic = 0
    for sub in submissions:
        sig = (sub.get("clinical_significance") or "").strip()
        if not sig or sig.lower() in _INVALID_SUBMISSION_SIGS:
            continue
        valid += 1
        if _submission_is_pathogenic(sig):
            pathogenic += 1
    if valid == 0:
        return False
    return (pathogenic / valid) * 100.0 >= threshold_pct


def clinvar_evidence(
    clinvar: dict[str, Any] | None, config: FilterConfig, *, conflicting_ok: bool
) -> bool:
    """Whether a variant has qualifying ClinVar evidence (standard or conflicting)."""
    if not config.clinvar_enabled or not clinvar:
        return False
    if is_pathogenic_clinvar(clinvar, config.clinvar_star_threshold):
        return True
    return config.include_conflicting and is_conflicting(clinvar) and conflicting_ok


def qualifies(
    consequence: dict[str, Any] | None,
    *,
    has_clinvar_evidence: bool,
    config: FilterConfig,
) -> bool:
    """The gnomad-carrier-frequency inclusion decision tree."""
    if config.lof_hc_enabled and is_hc_lof(consequence):
        return True
    if is_missense(consequence):
        return config.missense_enabled and has_clinvar_evidence
    return has_clinvar_evidence


# --- quality flags ---


def is_high_af(af: float, threshold: float = 0.05) -> bool:
    """ACMG BA1 high allele frequency flag."""
    return af >= threshold


def _failed_filters(source: dict[str, Any] | None) -> bool:
    if not source:
        return False
    filters = source.get("filters") or []
    return bool(filters) and filters != ["PASS"]


def is_gnomad_filtered(exome: dict[str, Any] | None, genome: dict[str, Any] | None) -> bool:
    """Variant failed gnomAD QC in exome or genome."""
    return _failed_filters(exome) or _failed_filters(genome)


def is_genomes_only(exome: dict[str, Any] | None, genome: dict[str, Any] | None) -> bool:
    """No exome data (genome-only call)."""
    if not genome:
        return False
    return exome is None or (exome.get("an") or 0) == 0


def is_high_hom(
    *,
    observed_hom: int,
    af: float,
    individuals: float,
    method: str = "hwe_relative",
    multiplier: float = 5.0,
    absolute_threshold: int = 10,
) -> bool:
    """High homozygote-count flag (HWE-relative excess or absolute count)."""
    if method == "absolute":
        return observed_hom >= absolute_threshold
    expected = hwe_expected_homozygotes(af, individuals)
    return observed_hom > multiplier * expected
