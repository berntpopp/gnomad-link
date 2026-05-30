"""Shape gnomAD coverage payloads into compact MCP responses.

Per-position coverage bins are the heaviest payload in the suite. Compact mode
trims each bin to a 4-field keep-set (plus pos), caps bins per source, and emits
a self-describing `truncated` block. The {mean_coverage, fraction_over_20}
summary is computed from the FULL bins BEFORE the cap so it stays accurate even
when the returned bins are truncated. Lives in its own module to keep
gnomad_link/mcp/shaping.py from growing.
"""

from __future__ import annotations

from typing import Any

# Compact keep-set per bin (pos always retained for gene/region bins).
_COMPACT_BIN_KEEP = {"pos", "mean", "median", "over_20", "over_30"}
# Scalar (variant-scope) coverage keep-set.
_SCALAR_KEEP = {"mean", "median", "over_20", "over_30"}


def _bin_summary(bins: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute {mean_coverage, fraction_over_20} from the FULL bin list."""
    means = [b["mean"] for b in bins if b.get("mean") is not None]
    over_20 = [b["over_20"] for b in bins if b.get("over_20") is not None]
    return {
        "mean_coverage": round(sum(means) / len(means), 4) if means else None,
        "fraction_over_20": round(sum(over_20) / len(over_20), 4) if over_20 else None,
    }


def _project_bin(b: dict[str, Any], *, compact: bool) -> dict[str, Any]:
    if not compact:
        return b
    return {k: v for k, v in b.items() if k in _COMPACT_BIN_KEEP}


def _shape_feature_source(
    bins: list[dict[str, Any]] | None, *, compact: bool, max_bins: int
) -> dict[str, Any]:
    """Shape one gene/region source (exome or genome) into bins+summary+truncated."""
    bins = bins or []
    summary = _bin_summary(bins)  # from FULL bins, before cap
    projected = [_project_bin(b, compact=compact) for b in bins]
    out: dict[str, Any] = {"bins": projected[:max_bins], "summary": summary}
    if len(projected) > max_bins:
        out["bins"] = projected[:max_bins]
        out["truncated"] = {
            "kind": "coverage_bins",
            "dropped": len(projected) - max_bins,
            "to_disable": "raise max_bins (the summary already reflects all bins)",
            "to_restore": f"max_bins={len(projected)}",
        }
    return out


def _shape_scalar_source(source: dict[str, Any] | None, *, compact: bool) -> dict[str, Any] | None:
    if source is None:
        return None
    if not compact:
        return source
    return {k: v for k, v in source.items() if k in _SCALAR_KEEP}


def shape_coverage_payload(
    raw: dict[str, Any],
    *,
    scope: str,
    dataset: str,
    response_mode: str,
    max_bins: int,
) -> dict[str, Any]:
    """Project a CoverageService payload into the get_coverage success shape."""
    compact = response_mode == "compact"

    if scope == "variant":
        feature = raw.get("variant") or {}
        coverage = feature.get("coverage") or {}
        return {
            "scope": "variant",
            "identity": {"variant_id": feature.get("variant_id")},
            "dataset": dataset,
            "exome": _shape_scalar_source(coverage.get("exome"), compact=compact),
            "genome": _shape_scalar_source(coverage.get("genome"), compact=compact),
        }

    if scope == "region":
        feature = raw.get("region") or {}
        identity = {
            "chrom": feature.get("chrom"),
            "start": feature.get("start"),
            "stop": feature.get("stop"),
        }
    else:  # gene
        feature = raw.get("gene") or {}
        identity = {"gene_id": feature.get("gene_id"), "symbol": feature.get("symbol")}

    coverage = feature.get("coverage") or {}
    return {
        "scope": scope,
        "identity": identity,
        "dataset": dataset,
        "exome": _shape_feature_source(coverage.get("exome"), compact=compact, max_bins=max_bins),
        "genome": _shape_feature_source(coverage.get("genome"), compact=compact, max_bins=max_bins),
    }
