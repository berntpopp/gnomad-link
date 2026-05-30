"""Client-side filtering, capping, and compact projection for SV search.

Upstream gene/region structural_variants fields take no filter arguments, so
all filtering (sv_type, min_length, max_length) and the limit cap happen here.
Pattern mirrors shaping.shape_gene_variants: total_seen reflects the FULL
list before any cap, and a self-describing truncated block reports the most
useful restore hint.
"""

from __future__ import annotations

from typing import Any

from gnomad_link.mcp.errors import ToolInputError

# Heavy per-variant histograms the compact single-variant view drops; callers
# recover them with response_mode='full'. cpx_intervals/copy_numbers stay (small
# and class-defining for complex/CNV variants).
_SV_HEAVY_FIELDS = ("age_distribution", "genotype_quality")


def shape_structural_variant(
    payload: dict[str, Any], *, response_mode: str = "compact"
) -> dict[str, Any]:
    """Compact a single structural-variant payload.

    Drops the heavy age/genotype-quality histograms and the duplicated flat
    top-level ``genes`` list (the same symbols are grouped, with their
    consequence, under ``consequences[].genes``). Emits a self-describing
    ``truncated`` block so the LLM can recover the full payload with
    ``response_mode='full'``. ``full`` returns the payload unchanged.
    """
    if response_mode == "full":
        return payload
    out = dict(payload)
    dropped: dict[str, Any] = {}
    for key in _SV_HEAVY_FIELDS:
        if out.pop(key, None) is not None:
            dropped[key] = "histogram"
    # Drop the duplicated flat gene list only when the richer grouped view is
    # present, so gene information is never lost.
    if out.get("genes") and out.get("consequences"):
        dropped["genes"] = len(out["genes"])
        out.pop("genes", None)
    if dropped:
        out["truncated"] = {
            "kind": "structural_variant",
            "dropped": dropped,
            "to_disable": "response_mode='full' returns histograms and the flat gene list",
            "to_restore": "response_mode='full'",
        }
    return out


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
        raise ToolInputError("limit must be in [1, 500]")

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
