"""Shape GeneCarrierService output into a compact MCP response.

Sorts populations by carrier frequency, adds ``1 in N`` reciprocals, caps the
contributing-variant list with a self-describing ``truncated`` block, and
attaches the assumptions note and citations. Kept out of shaping.py (LOC cap).
"""

from __future__ import annotations

from typing import Any

from gnomad_link.mcp.headline import gene_carrier_headline
from gnomad_link.mcp.provenance import provenance_block


def _one_in(value: float | None) -> int | None:
    if not value or value <= 0:
        return None
    return round(1.0 / value)


# The clean Pathogenic/Likely-pathogenic classifications — a variant carrying one
# of these has no penetrance caveat.
_CLEAN_PLP = {"pathogenic", "likely pathogenic", "pathogenic/likely pathogenic"}

# Qualifiers that, appended to a P/LP call, mark a REDUCED or VARIABLE penetrance
# allele — the CFTR-RD alleles (5T, R117H = "…; other") that make the ClinVar-P/LP
# gene-level estimate overstate CF carrier frequency (defect #45-1). These are NOT
# the same as a non-P/LP classification: Benign, Likely benign, Uncertain
# significance, and Conflicting classifications are simply NOT reduced-penetrance
# P/LP variants and must never be flagged as such (a Benign-annotated pLoF was
# being falsely flagged).
_REDUCED_PENETRANCE_QUALIFIERS = (
    "other",
    "risk factor",
    "association",
    "drug response",
    "protective",
    "affects",
    "low penetrance",
    "reduced penetrance",
)


def _penetrance_flag(clinvar_significance: str | None) -> str | None:
    """Flag ONLY a Pathogenic/Likely-pathogenic call carrying a reduced/variable-
    penetrance qualifier (e.g. "Pathogenic/Likely pathogenic; other").

    Returns None for a clean P/LP, and None for anything whose primary call is not
    P/LP (Benign / Likely benign / Uncertain significance / Conflicting …) — those
    are not reduced-penetrance P/LP variants, so flagging them would be a false
    positive.
    """
    if not clinvar_significance:
        return None
    sig = clinvar_significance.strip().lower()
    if sig in _CLEAN_PLP:
        return None
    # Primary call must be Pathogenic / Likely pathogenic (not "conflicting …",
    # which merely contains the substring "pathogenicity", and not benign/VUS).
    if not (sig.startswith("pathogenic") or sig.startswith("likely pathogenic")):
        return None
    if any(qualifier in sig for qualifier in _REDUCED_PENETRANCE_QUALIFIERS):
        return "reduced_or_variable"
    return None


def _round(value: Any, digits: int) -> Any:
    return round(value, digits) if isinstance(value, (int, float)) else value


def _shape_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    cf = metrics.get("carrier_frequency")
    gp = metrics.get("genetic_prevalence")
    return {
        "carrier_frequency": _round(cf, 6),
        "carrier_one_in": _one_in(cf),
        "genetic_prevalence": _round(gp, 8),
        "genetic_prevalence_one_in": _one_in(gp),
        "bayesian_prevalence": _round(metrics.get("bayesian_prevalence"), 8),
        "sum_af": _round(metrics.get("sum_af"), 6),
        "total_ac": metrics.get("total_ac"),
        "max_an": metrics.get("max_an"),
    }


def shape_gene_carrier(
    result: dict[str, Any],
    *,
    response_mode: str,
    top_variants_limit: int,
) -> dict[str, Any]:
    """Project a GeneCarrierService payload into the tool success shape."""
    settings = dict(result.get("settings") or {})
    settings.setdefault("omitted_populations", ["sex_split", "subcohort"])
    populations = [
        {"population": pop_id, **_shape_metrics(metrics)}
        for pop_id, metrics in (result.get("populations") or {}).items()
    ]
    populations.sort(key=lambda p: p.get("carrier_frequency") or 0.0, reverse=True)

    variants = sorted(
        result.get("qualifying_variants") or [],
        key=lambda v: v.get("global_af") or 0.0,
        reverse=True,
    )
    # Flag each variant whose ClinVar significance is present but not a clean P/LP
    # as reduced/variable penetrance, and count them across the FULL qualifying set
    # so the caveat holds even when the contributing list is capped.
    reduced_penetrance_variants = 0
    for v in variants:
        flag = _penetrance_flag(v.get("clinvar_significance"))
        if flag is not None:
            v["penetrance_flag"] = flag
            reduced_penetrance_variants += 1
    cap = len(variants) if response_mode == "full" else top_variants_limit
    contributing: dict[str, Any] = {
        "count": result.get("qualifying_count", len(variants)),
        "reduced_penetrance_variants": reduced_penetrance_variants,
        # `sources` is carried once at the top level of the shaped payload; do not
        # duplicate it inside contributing_variants.
        "top": variants[:cap],
    }
    if len(variants) > cap:
        contributing["truncated"] = {
            "kind": "contributing_variants",
            "dropped": len(variants) - cap,
            "to_disable": "raise top_variants_limit or response_mode='full'",
            "to_restore": "response_mode='full'",
        }

    shaped: dict[str, Any] = {
        "gene": result.get("gene"),
        "dataset": result.get("dataset"),
        "reference_genome": result.get("reference_genome"),
        "settings": settings,
        "global": _shape_metrics(result.get("global") or {}),
        "populations": populations,
        "contributing_variants": contributing,
        "sources": result.get("sources"),
    }
    degraded = result.get("conflicting_resolution_degraded")
    if degraded:
        shaped["degraded"] = degraded
    shaped.update(provenance_block("gene_carrier", full=response_mode == "full"))
    # Lead with the plain-English headline so an LLM can answer without parsing.
    return {"headline": gene_carrier_headline(shaped), **shaped}
