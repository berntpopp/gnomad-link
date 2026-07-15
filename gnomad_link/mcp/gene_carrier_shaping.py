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


# A ClinVar significance that is NOT one of these clean Pathogenic/Likely-pathogenic
# strings (e.g. "Pathogenic/Likely pathogenic; other", "; drug response",
# "conflicting ...") flags a variant as reduced/variable penetrance — the CFTR-RD
# alleles (5T, R117H) that make the ClinVar-P/LP gene-level estimate overstate CF
# carrier frequency (defect #45-1).
_CLEAN_PLP = {"pathogenic", "likely pathogenic", "pathogenic/likely pathogenic"}


def _penetrance_flag(clinvar_significance: str | None) -> str | None:
    """Return "reduced_or_variable" for a present-but-not-clean-P/LP significance."""
    if not clinvar_significance:
        return None
    if clinvar_significance.strip().lower() in _CLEAN_PLP:
        return None
    return "reduced_or_variable"


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
