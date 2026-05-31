"""Heteroplasmy histogram trimming for mitochondrial variant responses.

The gnomAD GraphQL ``heteroplasmy_distribution`` histogram ships many empty
bins by default. Hot-Fix H3 trims zero-count bins by default (both at the
variant-level and per-population scope) and exposes an opt-out so callers can
recover the full histogram when needed. When trimming fires we emit a
self-describing ``truncated.kind="heteroplasmy_zeros"`` block alongside the
payload — mirroring the pattern used elsewhere in :mod:`gnomad_link.mcp.shaping`.
"""

from __future__ import annotations

from typing import Any

from gnomad_link.mcp.population_shaping import is_sex_split


def trim_heteroplasmy_distribution(
    dist: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, int]:
    """Drop zero-count bins from a heteroplasmy histogram.

    Returns ``(trimmed_or_None, dropped_count)``. All-zero histograms collapse
    to ``None`` so the caller drops the key. Non-bin metadata (``n_smaller``,
    ``n_larger``) is preserved. Mismatched or missing inputs pass through
    unchanged with ``dropped_count == 0``.
    """

    if not isinstance(dist, dict):
        return dist, 0
    edges, freqs = dist.get("bin_edges"), dist.get("bin_freq")
    if not isinstance(edges, list) or not isinstance(freqs, list):
        return dist, 0
    # gnomAD histograms carry N+1 edges for N bins; treat the leading N edges as
    # per-bin lower bounds and drop the trailing closing edge so edges align with
    # freqs. (Without this the length guard never matched real data and trimming
    # silently never fired.) Any other length mismatch passes through unchanged.
    if len(edges) == len(freqs) + 1:
        edges = edges[:-1]
    elif len(edges) != len(freqs):
        return dist, 0
    pairs = [
        (e, f)
        for e, f in zip(edges, freqs, strict=True)
        if not (isinstance(f, int | float) and f == 0)
    ]
    dropped = len(freqs) - len(pairs)
    if not pairs:
        return None, dropped
    trimmed = dict(dist)
    trimmed["bin_edges"] = [e for e, _ in pairs]
    trimmed["bin_freq"] = [f for _, f in pairs]
    return trimmed, dropped


def _apply_het_trim(holder: dict[str, Any]) -> int:
    """Mutate ``holder`` to drop zero-count heteroplasmy bins; return drop count."""

    original = holder.get("heteroplasmy_distribution")
    trimmed, dropped = trim_heteroplasmy_distribution(original)
    if trimmed is None and original is not None:
        holder.pop("heteroplasmy_distribution", None)
    elif trimmed is not None:
        holder["heteroplasmy_distribution"] = trimmed
    return dropped


def _is_zero_mito_row(row: dict[str, Any]) -> bool:
    """A mito population/haplogroup row carries no allele evidence."""

    return (row.get("ac_het") or 0) == 0 and (row.get("ac_hom") or 0) == 0


def shape_mitochondrial_variant(
    payload: dict[str, Any], *, include_heteroplasmy_zeros: bool
) -> dict[str, Any]:
    """Trim zero-signal heteroplasmy bins and population/haplogroup rows.

    When ``include_heteroplasmy_zeros`` is True the payload is returned
    unchanged (full-detail escape hatch). Otherwise, in addition to dropping
    zero-count heteroplasmy bins (variant-level and per-population), the compact
    view also trims:

    * ``populations`` rows that carry no signal (``ac_het == 0 and ac_hom == 0``)
      or that are ``_XX``/``_XY`` sex splits;
    * ``haplogroups`` rows that carry no signal (haplogroups are not sex-split).

    Kept rows are passed through verbatim. A single
    ``truncated.kind="heteroplasmy_zeros"`` block reports all drops together via
    a ``dropped`` mapping (``heteroplasmy_bins``/``populations``/``haplogroups``,
    nonzero keys only) and the one knob that restores everything.
    """

    if include_heteroplasmy_zeros:
        return payload
    out = dict(payload)
    bins_dropped = _apply_het_trim(out)
    populations = out.get("populations")
    pops_dropped = 0
    if isinstance(populations, list):
        new_pops: list[Any] = []
        for pop in populations:
            if isinstance(pop, dict):
                if _is_zero_mito_row(pop) or is_sex_split(pop.get("id") or ""):
                    pops_dropped += 1
                    continue
                pop_copy = dict(pop)
                bins_dropped += _apply_het_trim(pop_copy)
                new_pops.append(pop_copy)
            else:
                new_pops.append(pop)
        out["populations"] = new_pops
    haplogroups = out.get("haplogroups")
    haplos_dropped = 0
    if isinstance(haplogroups, list):
        new_haplos = [h for h in haplogroups if not (isinstance(h, dict) and _is_zero_mito_row(h))]
        haplos_dropped = len(haplogroups) - len(new_haplos)
        if haplos_dropped > 0:
            out["haplogroups"] = new_haplos
    total = bins_dropped + pops_dropped + haplos_dropped
    if total > 0:
        dropped: dict[str, int] = {}
        if bins_dropped:
            dropped["heteroplasmy_bins"] = bins_dropped
        if pops_dropped:
            dropped["populations"] = pops_dropped
        if haplos_dropped:
            dropped["haplogroups"] = haplos_dropped
        out["truncated"] = {
            "kind": "heteroplasmy_zeros",
            "dropped": dropped,
            "to_disable": "set include_heteroplasmy_zeros=True for the full histogram",
            "to_restore": "include_heteroplasmy_zeros=True",
        }
    return out
