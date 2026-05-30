"""Pure helpers that align per-dataset variant-frequency shapes for comparison.

compare_variant_across_datasets calls get_variant_frequencies per dataset and
reuses shape_variant_frequencies to produce one compact dict per dataset. This
module consumes those already-shaped dicts (wrapped as {"present": True, ...} or
{"present": False}) and produces the top-level `comparison` block: overall AF by
dataset plus per-population AF deltas. No service or network access here.
"""

from __future__ import annotations

from typing import Any


def _iter_population_rows(shaped: dict[str, Any]) -> dict[str, float]:
    """Return {population_id: af} for one shaped dataset dict.

    Reads both exome and genome population lists. When the same population id is
    present in both sources, the higher AF wins so the recorded per-dataset value
    is the most-enriched observed allele frequency (mirrors shaping._top_enriched_population).
    Rows with af is None are skipped.
    """
    by_pop: dict[str, float] = {}
    for source_key in ("exome", "genome"):
        source = shaped.get(source_key)
        if not source:
            continue
        for pop in source.get("populations", []):
            pop_id = pop.get("id")
            af = pop.get("af")
            if pop_id is None or af is None:
                continue
            existing = by_pop.get(pop_id)
            if existing is None or af > existing:
                by_pop[pop_id] = af
    return by_pop


def build_comparison(per_dataset: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Assemble the comparison block from per-dataset shaped dicts.

    Args:
        per_dataset: dataset name -> {"present": bool, ...shaped frequency dict}.
            Absent datasets are {"present": False} and are skipped.

    Returns:
        {
            "overall_af_by_dataset": {dataset: overall_af, ...},
            "per_population_af_deltas": [
                {"population": str, "af_by_dataset": {dataset: af, ...},
                 "max_minus_min_delta": float},
                ...  # sorted by max_minus_min_delta descending, then population asc
            ],
        }
    """
    overall_af_by_dataset: dict[str, float] = {}
    # population -> dataset -> af
    af_by_pop_dataset: dict[str, dict[str, float]] = {}

    for dataset, entry in per_dataset.items():
        if not entry.get("present"):
            continue
        summary = entry.get("summary") or {}
        overall_af = summary.get("overall_af")
        if overall_af is not None:
            overall_af_by_dataset[dataset] = overall_af
        for pop_id, af in _iter_population_rows(entry).items():
            af_by_pop_dataset.setdefault(pop_id, {})[dataset] = af

    deltas: list[dict[str, Any]] = []
    for pop_id, af_by_dataset in af_by_pop_dataset.items():
        values = list(af_by_dataset.values())
        delta = (max(values) - min(values)) if len(values) > 1 else 0.0
        deltas.append(
            {
                "population": pop_id,
                "af_by_dataset": af_by_dataset,
                "max_minus_min_delta": delta,
            }
        )
    deltas.sort(key=lambda row: (-row["max_minus_min_delta"], row["population"]))

    return {
        "overall_af_by_dataset": overall_af_by_dataset,
        "per_population_af_deltas": deltas,
    }
