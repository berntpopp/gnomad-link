"""Client-side filtering, capping, and compact projection for SV search.

Upstream gene/region structural_variants fields take no filter arguments, so
all filtering (sv_type, min_length, max_length) and the limit cap happen here.
Pattern mirrors shaping.shape_gene_variants: total_seen reflects the FULL
list before any cap, and a self-describing truncated block reports the most
useful restore hint.
"""

from __future__ import annotations

from typing import Any

# Compact projection key-set. Drops heavy fields (consequences, populations,
# cpx_intervals, ...) the list view does not need; callers fetch the full
# payload per id via get_structural_variant.
_SV_ROW_KEEP = {
    "variant_id",
    "type",
    "chrom",
    "pos",
    "end",
    "length",
    "af",
    "ac",
    "an",
    "major_consequence",
}


def _project_sv_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k in _SV_ROW_KEEP}


def shape_sv_search(
    raw: list[dict[str, Any]],
    *,
    sv_type: str | None,
    min_length: int | None,
    max_length: int | None,
    limit: int,
) -> dict[str, Any]:
    """Filter, cap, and compact-project a structural-variant list.

    Filtering is case-insensitive on sv_type. min_length/max_length apply to
    each row's `length`; rows without a length are dropped when a length
    filter is active. Emits a `truncated` block when any filter drops rows or
    when the limit cap fires; `total_seen` always reflects the FULL input.
    """
    if limit <= 0 or limit > 500:
        raise ValueError("limit must be in [1, 500]")

    total_seen = len(raw)
    dropped = {"by_sv_type": 0, "by_min_length": 0, "by_max_length": 0}
    wanted_type = sv_type.upper() if sv_type else None

    filtered: list[dict[str, Any]] = []
    for row in raw:
        if wanted_type is not None and str(row.get("type") or "").upper() != wanted_type:
            dropped["by_sv_type"] += 1
            continue
        length = row.get("length")
        if min_length is not None and (length is None or length < min_length):
            dropped["by_min_length"] += 1
            continue
        if max_length is not None and (length is None or length > max_length):
            dropped["by_max_length"] += 1
            continue
        filtered.append(row)

    capped = filtered[:limit]
    cap_dropped = len(filtered) - len(capped)
    rows = [_project_sv_row(r) for r in capped]

    payload: dict[str, Any] = {
        "structural_variants": rows,
        "returned": len(rows),
        "total_seen": total_seen,
    }

    any_filter_dropped = sum(dropped.values()) > 0
    if any_filter_dropped or cap_dropped > 0:
        # Restore hint targets the cap first (a single int bump), then the
        # most-dropped filter category.
        restore_mapping = {
            "by_sv_type": "sv_type=None (remove type filter)",
            "by_min_length": "min_length=None (remove length floor)",
            "by_max_length": "max_length=None (remove length ceiling)",
        }
        if cap_dropped > 0:
            to_restore: str | None = f"limit={min(len(filtered), 500)}"
        else:
            best_key: str | None = None
            best_count = 0
            for key, count in dropped.items():
                if count > best_count:
                    best_count = count
                    best_key = key
            to_restore = restore_mapping.get(best_key or "")
        truncated: dict[str, Any] = {
            "kind": "structural_variants",
            "dropped": sum(dropped.values()) + cap_dropped,
            "filter": {
                "sv_type": sv_type,
                "min_length": min_length,
                "max_length": max_length,
            },
            "to_disable": ("raise limit (max 500) or relax sv_type/min_length/max_length filters"),
        }
        if to_restore:
            truncated["to_restore"] = to_restore
        payload["truncated"] = truncated

    return payload
