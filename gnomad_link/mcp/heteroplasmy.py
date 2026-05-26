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
    if not isinstance(edges, list) or not isinstance(freqs, list) or len(edges) != len(freqs):
        return dist, 0
    pairs = [
        (e, f)
        for e, f in zip(edges, freqs, strict=True)
        if not (isinstance(f, int | float) and f == 0)
    ]
    dropped = len(edges) - len(pairs)
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


def shape_mitochondrial_variant(
    payload: dict[str, Any], *, include_heteroplasmy_zeros: bool
) -> dict[str, Any]:
    """Trim zero-count heteroplasmy bins at variant + per-population scope.

    When ``include_heteroplasmy_zeros`` is True the payload is returned
    unchanged. Otherwise zero-count bins are dropped from the variant-level
    and per-population histograms, and a ``truncated.kind="heteroplasmy_zeros"``
    block reports the total dropped count and how to restore the full payload.
    """

    if include_heteroplasmy_zeros:
        return payload
    out = dict(payload)
    total = _apply_het_trim(out)
    populations = out.get("populations")
    if isinstance(populations, list):
        new_pops: list[Any] = []
        for pop in populations:
            if isinstance(pop, dict):
                pop_copy = dict(pop)
                total += _apply_het_trim(pop_copy)
                new_pops.append(pop_copy)
            else:
                new_pops.append(pop)
        out["populations"] = new_pops
    if total > 0:
        out["truncated"] = {
            "kind": "heteroplasmy_zeros",
            "dropped": total,
            "to_disable": "set include_heteroplasmy_zeros=True for the full histogram",
            "to_restore": "include_heteroplasmy_zeros=True",
        }
    return out
