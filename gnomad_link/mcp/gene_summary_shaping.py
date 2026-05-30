"""Pure helpers that compact GeneSummaryService payloads for get_gene_summary.

Kept out of shaping.py (at its LOC ceiling). Mirrors the conventions in
shaping.py: stable sorts, self-describing ``truncated`` blocks with
``to_disable``/``to_restore`` hints, and compact row projection.
"""

from __future__ import annotations

from typing import Any

# Keys advertised in the compact top_pathogenic block.
_PATHOGENIC_ROW_KEEP = ("variant_id", "clinical_significance", "gold_stars", "major_consequence")


def _is_pathogenic(significance: str | None) -> bool:
    """True for ClinVar Pathogenic / Likely pathogenic (and combined) classifications."""
    if not significance:
        return False
    return "pathogenic" in significance.lower()


def _project_pathogenic_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: row.get(k) for k in _PATHOGENIC_ROW_KEEP}


def rank_pathogenic_clinvar(
    clinvar_variants: list[dict[str, Any]], *, clinvar_limit: int
) -> dict[str, Any]:
    """Filter to P/LP rows, sort by gold_stars desc, cap at clinvar_limit.

    Returns a block with ``pathogenic_count`` (total P/LP before the cap),
    ``top_pathogenic`` (capped, compact rows), and a self-describing
    ``truncated`` block when the cap drops rows. ``gold_stars`` of None ranks
    below any explicit star count; ties preserve original order.
    """
    pathogenic = [r for r in clinvar_variants if _is_pathogenic(r.get("clinical_significance"))]
    ranked = sorted(
        enumerate(pathogenic),
        key=lambda item: (-(item[1].get("gold_stars") or 0), item[0]),
    )
    ordered = [row for _, row in ranked]
    capped = ordered[:clinvar_limit]
    block: dict[str, Any] = {
        "pathogenic_count": len(pathogenic),
        "top_pathogenic": [_project_pathogenic_row(r) for r in capped],
    }
    if len(ordered) > clinvar_limit:
        block["truncated"] = {
            "kind": "pathogenic_clinvar",
            "dropped": len(ordered) - clinvar_limit,
            "filter": {"clinvar_limit": clinvar_limit},
            "to_disable": "raise clinvar_limit (max 50) or response_mode='full'",
            "to_restore": "response_mode='full'",
        }
    return block


def _mean_pext(pext: dict[str, Any] | None) -> float | None:
    if not pext:
        return None
    regions = pext.get("regions") or []
    means: list[float] = [float(r["mean"]) for r in regions if r.get("mean") is not None]
    if not means:
        return None
    return round(sum(means) / len(means), 4)


def compact_expression(
    *,
    pext: dict[str, Any] | None,
    gtex_tissue_expression: list[dict[str, Any]] | None,
    source_build: str = "GRCh38",
) -> dict[str, Any]:
    """Compact expression: mean pext + top-5 GTEx tissues for the canonical transcript.

    pext is read from ``gene.pext`` and GTEx from the canonical transcript's
    ``gtex_tissue_expression`` (both available on GRCh38). Returns
    ``{"unavailable": True, "note": ...}`` only when neither pext regions nor
    GTEx tissue values are present.
    """
    mean_pext = _mean_pext(pext)
    tissues = [t for t in (gtex_tissue_expression or []) if t.get("value") is not None]
    if mean_pext is None and not tissues:
        return {
            "unavailable": True,
            "note": "Expression (pext/GTEx) is empty for this gene in gnomAD.",
        }
    top_tissues = sorted(tissues, key=lambda t: t.get("value") or 0.0, reverse=True)[:5]
    return {
        "source_build": source_build,
        "mean_pext": mean_pext,
        "top_tissues": [{"tissue": t.get("tissue"), "value": t.get("value")} for t in top_tissues],
    }
