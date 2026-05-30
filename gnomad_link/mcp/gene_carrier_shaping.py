"""Shape GeneCarrierService output into a compact MCP response.

Sorts populations by carrier frequency, adds ``1 in N`` reciprocals, caps the
contributing-variant list with a self-describing ``truncated`` block, and
attaches the assumptions note and citations. Kept out of shaping.py (LOC cap).
"""

from __future__ import annotations

from typing import Any

_ASSUMPTIONS_NOTE = (
    "Gene-level estimate: sums qualifying pathogenic variants under Hardy-Weinberg "
    "equilibrium (random mating, complete penetrance unless penetrance<1). Carrier "
    "frequency uses the selected method (hom_exclusion=GCR is the default). A minimum "
    "estimate bounded by gnomAD ascertainment and ClinVar completeness; not clinical "
    "decision support."
)
_CITATIONS = (
    "Karczewski et al. 2022 (PMC9763236) - variant/gene carrier rate.",
    "Schrodi et al. 2015, Hum Genet, doi:10.1007/s00439-015-1551-8 - 2pq carrier framework.",
    "Karczewski et al. 2020, Nature - gnomAD allele frequencies.",
)


def _one_in(value: float | None) -> int | None:
    if not value or value <= 0:
        return None
    return round(1.0 / value)


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
    cap = len(variants) if response_mode == "full" else top_variants_limit
    contributing: dict[str, Any] = {
        "count": result.get("qualifying_count", len(variants)),
        "sources": result.get("sources"),
        "top": variants[:cap],
    }
    if len(variants) > cap:
        contributing["truncated"] = {
            "kind": "contributing_variants",
            "dropped": len(variants) - cap,
            "to_disable": "raise top_variants_limit or response_mode='full'",
            "to_restore": "response_mode='full'",
        }

    return {
        "gene": result.get("gene"),
        "dataset": result.get("dataset"),
        "reference_genome": result.get("reference_genome"),
        "settings": result.get("settings"),
        "global": _shape_metrics(result.get("global") or {}),
        "populations": populations,
        "contributing_variants": contributing,
        "sources": result.get("sources"),
        "assumptions_note": _ASSUMPTIONS_NOTE,
        "citations": list(_CITATIONS),
    }
