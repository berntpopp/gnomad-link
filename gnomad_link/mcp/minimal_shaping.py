"""Per-tool ``response_mode='minimal'`` projectors for the headline tools.

Each projector takes the tool's already-computed *compact* payload (the dict the
tool would return for ``response_mode='compact'``, carrying its ``headline`` and
``_meta.next_commands``) and projects it to a tight top-line subset: the
headline, the global/summary block, and the full ``_meta``, plus a
self-describing ``truncated`` block naming what was dropped.

The projection is deliberately a *selection over the compact payload* (not a
re-derivation): field names therefore match compact exactly. Heavy arrays
(per-population rows, transcripts, the contributing-variant list, the
per-population AF deltas, raw per-dataset frequency rows) are dropped.

Groundability is preserved: every minimal payload keeps the full ``_meta``
(``next_commands`` + ``unsafe_for_clinical_use`` + provenance, the latter merged
later by ``run_mcp_tool``) so a minimal answer is never less citable than a
compact one.
"""

from __future__ import annotations

from typing import Any

_RESTORE = "response_mode='compact'"


def _truncated(dropped: list[str]) -> dict[str, Any]:
    """Build the standard minimal-mode ``truncated`` block."""
    return {"kind": "minimal_mode", "dropped": dropped, "to_restore": _RESTORE}


def _base(compact: dict[str, Any]) -> dict[str, Any]:
    """Seed a minimal payload with the headline (if any) and _meta (verbatim)."""
    out: dict[str, Any] = {}
    if "headline" in compact:
        out["headline"] = compact["headline"]
    if "_meta" in compact:
        out["_meta"] = compact["_meta"]
    return out


def project_variant_frequencies_minimal(compact: dict[str, Any]) -> dict[str, Any]:
    """get_variant_frequencies: keep id/dataset/consequence + the summary block.

    Drops the exome/genome per-population frequency arrays.
    """
    out = _base(compact)
    for key in ("variant_id", "dataset", "gene_symbol", "major_consequence"):
        if key in compact:
            out[key] = compact[key]
    if "summary" in compact:
        out["summary"] = compact["summary"]
    out["truncated"] = _truncated(["exome", "genome"])
    return out


def project_carrier_frequency_minimal(compact: dict[str, Any]) -> dict[str, Any]:
    """compute_carrier_frequency: keep the global ``overall`` block + inheritance.

    Drops the per-population rows and the full citation list (citations_ref
    stays so the claim is still groundable).
    """
    out = _base(compact)
    for key in ("variant_id", "dataset", "inheritance", "method"):
        if key in compact:
            out[key] = compact[key]
    if "overall" in compact:
        out["overall"] = compact["overall"]
    if "summary" in compact:
        out["summary"] = compact["summary"]
    if "citations_ref" in compact:
        out["citations_ref"] = compact["citations_ref"]
    out["truncated"] = _truncated(["per_population", "citations", "assumptions_note"])
    return out


def project_gene_carrier_frequency_minimal(compact: dict[str, Any]) -> dict[str, Any]:
    """compute_gene_carrier_frequency: keep the ``global`` block + a variant COUNT.

    Drops the per-population rows and the contributing-variant list (only the
    count survives) and the full citation list.
    """
    out = _base(compact)
    for key in ("gene", "dataset", "reference_genome"):
        if key in compact:
            out[key] = compact[key]
    if "global" in compact:
        out["global"] = compact["global"]
    contributing = compact.get("contributing_variants")
    if isinstance(contributing, dict) and "count" in contributing:
        out["contributing_variants"] = {"count": contributing["count"]}
    if "citations_ref" in compact:
        out["citations_ref"] = compact["citations_ref"]
    out["truncated"] = _truncated(
        ["populations", "contributing_variants.top", "citations", "assumptions_note"]
    )
    return out


def project_gene_details_minimal(compact: dict[str, Any]) -> dict[str, Any]:
    """get_gene_details: keep symbol/gene_id + gnomad_constraint + coordinates.

    Drops the constraint matrix detail only by keeping pLI + LoF o/e; heavy
    arrays (transcripts/exons/alt_transcripts) are already absent in compact.
    """
    out = _base(compact)
    for key in ("gene_id", "symbol", "name", "chrom", "start", "stop", "strand"):
        if key in compact:
            out[key] = compact[key]
    constraint = compact.get("gnomad_constraint")
    if isinstance(constraint, dict):
        slim: dict[str, Any] = {}
        for key in ("pli", "oe_lof"):
            if key in constraint:
                slim[key] = constraint[key]
        out["gnomad_constraint"] = slim
    elif "gnomad_constraint" in compact:
        out["gnomad_constraint"] = compact["gnomad_constraint"]
    out["truncated"] = _truncated(["gnomad_constraint(full matrix)"])
    return out


def project_gene_summary_minimal(compact: dict[str, Any]) -> dict[str, Any]:
    """get_gene_summary: keep top-line constraint + ClinVar pathogenic COUNT.

    Drops the per-category ClinVar breakdown (``top_pathogenic`` rows) and the
    expression detail; keeps ``clinvar_summary.pathogenic_count``.
    """
    out = _base(compact)
    for key in ("gene_id", "symbol", "name", "coords", "dataset", "reference_genome"):
        if key in compact:
            out[key] = compact[key]
    if "constraint" in compact:
        out["constraint"] = compact["constraint"]
    summary = compact.get("clinvar_summary")
    if isinstance(summary, dict) and "pathogenic_count" in summary:
        out["clinvar_summary"] = {"pathogenic_count": summary["pathogenic_count"]}
    out["truncated"] = _truncated(
        ["clinvar_summary.top_pathogenic", "expression", "mane_select_transcript"]
    )
    return out


def project_compare_variant_minimal(compact: dict[str, Any]) -> dict[str, Any]:
    """compare_variant_across_datasets: keep per-dataset ``present`` + global AF.

    Drops the per-dataset raw frequency rows (exome/genome/summary) and the
    ``per_population_af_deltas`` detail; keeps ``comparison.overall_af_by_dataset``.
    """
    out = _base(compact)
    if "variant_id" in compact:
        out["variant_id"] = compact["variant_id"]
    datasets = compact.get("datasets")
    if isinstance(datasets, dict):
        slim_datasets: dict[str, Any] = {}
        for name, entry in datasets.items():
            if isinstance(entry, dict):
                slim: dict[str, Any] = {"present": entry.get("present")}
                if "lifted_variant_id" in entry:
                    slim["lifted_variant_id"] = entry["lifted_variant_id"]
                slim_datasets[name] = slim
            else:
                slim_datasets[name] = entry
        out["datasets"] = slim_datasets
    comparison = compact.get("comparison")
    if isinstance(comparison, dict) and "overall_af_by_dataset" in comparison:
        out["comparison"] = {"overall_af_by_dataset": comparison["overall_af_by_dataset"]}
    if "build_notes" in compact:
        out["build_notes"] = compact["build_notes"]
    out["truncated"] = _truncated(
        ["datasets.*.exome", "datasets.*.genome", "comparison.per_population_af_deltas"]
    )
    return out
