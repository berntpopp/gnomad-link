"""Pure helpers that project gnomAD service responses into MCP-compact shapes."""

from __future__ import annotations

from typing import Any

from gnomad_link.mcp.errors import ToolInputError
from gnomad_link.mcp.heteroplasmy import (
    shape_mitochondrial_variant,
    trim_heteroplasmy_distribution,
)
from gnomad_link.mcp.population_shaping import (
    BASE_POPULATION_CODES,
    build_populations_truncated,
    filter_populations,
    population_projection_note,
    project_variant_source,
)
from gnomad_link.models import VariantFrequencyResponse

__all__ = [
    "shape_mitochondrial_variant",
    "trim_heteroplasmy_distribution",
]


def _shape_source(
    source: Any,
    *,
    select: list[str] | None,
    include_subcohorts: bool,
    include_sex_split: bool,
    exclude_zero: bool,
) -> dict[str, Any] | None:
    if source is None:
        return None
    ac = getattr(source, "ac", 0)
    an = getattr(source, "an", 0)
    populations, dropped = filter_populations(
        getattr(source, "populations", []),
        select=select,
        include_subcohorts=include_subcohorts,
        include_sex_split=include_sex_split,
        exclude_zero=exclude_zero,
    )
    out: dict[str, Any] = {
        "ac": ac,
        "an": an,
        "af": (ac / an) if an else None,
        "homozygote_count": getattr(source, "homozygote_count", 0),
        "hemizygote_count": getattr(source, "hemizygote_count", None),
        "populations": populations,
    }
    truncated = build_populations_truncated(
        dropped,
        select=select,
        include_subcohorts=include_subcohorts,
        include_sex_split=include_sex_split,
        exclude_zero=exclude_zero,
    )
    if truncated:
        out["truncated"] = truncated
    return out


def _top_enriched_population(
    exome: dict[str, Any] | None, genome: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Pick the highest-AF base-population row across exome+genome for LLM summary.

    Restricted to BASE_POPULATION_CODES so subcohorts, sex-split, and other rows
    cannot win the summary slot — keeps the field interpretable for the LLM.
    """

    best: dict[str, Any] | None = None
    for source_name, source in (("exome", exome), ("genome", genome)):
        if not source:
            continue
        for pop in source.get("populations", []):
            if pop["id"] not in BASE_POPULATION_CODES:
                continue
            af = pop.get("af")
            if af is None:
                continue
            if best is None or af > best["af"]:
                best = {"id": pop["id"], "af": af, "source": source_name}
    return best


def _overall_af(exome: dict[str, Any] | None, genome: dict[str, Any] | None) -> float | None:
    """Compute a combined overall AF from the largest source by AN."""
    best_an = 0
    best_af: float | None = None
    for source in (exome, genome):
        if not source:
            continue
        an = source.get("an") or 0
        af = source.get("af")
        if an > best_an and af is not None:
            best_an = an
            best_af = af
    return best_af


def shape_variant_frequencies(
    response: VariantFrequencyResponse | dict[str, Any],
    *,
    populations: list[str] | None,
    include_subcohorts: bool,
    include_sex_split: bool,
    exclude_zero_populations: bool,
) -> dict[str, Any]:
    if isinstance(response, dict):
        response = VariantFrequencyResponse.model_validate(response)
    exome = _shape_source(
        response.exome,
        select=populations,
        include_subcohorts=include_subcohorts,
        include_sex_split=include_sex_split,
        exclude_zero=exclude_zero_populations,
    )
    genome = _shape_source(
        response.genome,
        select=populations,
        include_subcohorts=include_subcohorts,
        include_sex_split=include_sex_split,
        exclude_zero=exclude_zero_populations,
    )
    payload: dict[str, Any] = {
        "variant_id": response.variant_id,
        "dataset": response.dataset,
        "gene_symbol": response.gene_symbol,
        "major_consequence": response.major_consequence,
        "exome": exome,
        "genome": genome,
    }
    top = _top_enriched_population(exome, genome)
    overall = _overall_af(exome, genome)
    if top is not None or overall is not None:
        summary: dict[str, Any] = {}
        if top is not None:
            summary["top_enriched_population"] = top
            summary["max_pop"] = top["id"]
            summary["max_pop_af"] = top["af"]
        if overall is not None:
            summary["overall_af"] = overall
        # Placeholder: set to None to indicate unknown without get_clinvar_variant_details call.
        summary["has_clinvar"] = None
        payload["summary"] = summary
    return payload


def _project_gene_variant(
    v: dict[str, Any],
    *,
    select: list[str] | None,
    include_subcohorts: bool,
    include_sex_split: bool,
    exclude_zero: bool,
    include_populations: bool,
) -> dict[str, Any]:
    """Return a copy of a gene-variant row with its exome/genome populations trimmed."""
    out = dict(v)
    for source_key in ("exome", "genome"):
        if isinstance(out.get(source_key), dict):
            out[source_key] = project_variant_source(
                out[source_key],
                select=select,
                include_subcohorts=include_subcohorts,
                include_sex_split=include_sex_split,
                exclude_zero=exclude_zero,
                include_populations=include_populations,
                emit_truncated=False,
            )
    return out


def shape_gene_variants(
    raw: list[dict[str, Any]],
    *,
    limit: int,
    consequence: str | None,
    max_af: float | None,
    min_ac: int | None,
    include_populations: bool = True,
    include_subcohorts: bool = False,
    include_sex_split: bool = False,
    exclude_zero_populations: bool = True,
) -> dict[str, Any]:
    """Filter and cap a gene-variants list. Always returns a `truncated` block when the cap fires.

    Each kept row's exome/genome population breakdown is trimmed through the same
    projector as the single-variant tools (drop subcohort, sex-split, and zero-AC
    rows by default; ``include_populations=False`` drops the arrays entirely for
    list scans). The projection is reported once via a payload-level
    ``population_projection`` note rather than per-row ``truncated`` blocks.
    """

    if limit <= 0 or limit > 500:
        raise ToolInputError("limit must be in [1, 500]")
    filtered: list[dict[str, Any]] = []
    total_seen = 0
    dropped = {"by_consequence": 0, "by_max_af": 0, "by_min_ac": 0}
    for v in raw:
        total_seen += 1
        if (
            consequence
            and v.get("consequence") != consequence
            and v.get("major_consequence") != consequence
        ):
            dropped["by_consequence"] += 1
            continue
        if max_af is not None and (v.get("af") or 0.0) > max_af:
            dropped["by_max_af"] += 1
            continue
        if min_ac is not None and (v.get("ac") or 0) < min_ac:
            dropped["by_min_ac"] += 1
            continue
        filtered.append(
            _project_gene_variant(
                v,
                select=None,
                include_subcohorts=include_subcohorts,
                include_sex_split=include_sex_split,
                exclude_zero=exclude_zero_populations,
                include_populations=include_populations,
            )
        )
        if len(filtered) >= limit:
            break
    payload: dict[str, Any] = {
        "variants": filtered,
        "returned": len(filtered),
        "total_seen": total_seen,
    }
    # One payload-level note describing the per-variant population projection,
    # unless the caller explicitly asked for the full untrimmed breakdown.
    full_passthrough = (
        include_populations
        and include_subcohorts
        and include_sex_split
        and not exclude_zero_populations
    )
    if filtered and not full_passthrough:
        payload["population_projection"] = population_projection_note(
            select=None,
            include_subcohorts=include_subcohorts,
            include_sex_split=include_sex_split,
            exclude_zero=exclude_zero_populations,
            include_populations=include_populations,
        )
    limit_hit = len(filtered) >= limit and total_seen < len(raw)
    any_dropped = sum(dropped.values()) > 0
    if limit_hit or any_dropped or total_seen > len(filtered):
        # Find the most-dropped filter category to surface as to_restore.
        best_drop_key: str | None = None
        best_drop_count = 0
        for key, count in dropped.items():
            if count > best_drop_count:
                best_drop_count = count
                best_drop_key = key
        restore_mapping = {
            "by_consequence": "consequence=None (remove consequence filter)",
            "by_max_af": "max_af=None (remove AF ceiling)",
            "by_min_ac": "min_ac=None (remove AC floor)",
        }
        to_restore = restore_mapping.get(best_drop_key or "")
        gene_truncated: dict[str, Any] = {
            "kind": "gene_variants",
            "dropped": dropped,
            "filter": {
                "limit": limit,
                "consequence": consequence,
                "max_af": max_af,
                "min_ac": min_ac,
            },
            "to_disable": "raise limit (max 500) or relax max_af/min_ac/consequence filters",
        }
        if to_restore:
            gene_truncated["to_restore"] = to_restore
        payload["truncated"] = gene_truncated
    return payload


def _rank_transcript(tx: dict[str, Any]) -> int:
    """Rank transcripts so canonical/MANE win the cap, then protein_coding, then others."""

    if tx.get("canonical") or tx.get("mane_select"):
        return 0
    if tx.get("biotype") == "protein_coding":
        return 1
    return 2


def shape_variant_details_compact(
    raw: dict[str, Any],
    *,
    max_transcripts: int = 10,
    populations: list[str] | None = None,
    include_subcohorts: bool = False,
    include_sex_split: bool = False,
    exclude_zero_populations: bool = True,
) -> dict[str, Any]:
    """Project the gnomAD variant payload to the compact subset advertised in VariantDetails.

    Caps ``transcript_consequences`` at ``max_transcripts`` entries and emits a
    self-describing ``truncated`` block so the LLM can request the full payload
    with ``response_mode='full'``. Within the cap, canonical / MANE-Select
    transcripts win the slots first, then ``protein_coding`` entries, then the
    rest; original order is preserved within each rank tier.

    The exome/genome population breakdowns are trimmed through the same projector
    as ``get_variant_frequencies`` (drop subcohort, sex-split, and zero-AC rows by
    default); each source gains its own ``truncated.kind == "populations"`` block
    when rows are dropped. QC ``filters`` and source-level counts are preserved.
    """

    keep = {
        "variant_id",
        "reference_genome",
        "pos",
        "ref",
        "alt",
        "rsids",
        "major_consequence",
        "transcript_consequences",
        "in_silico_predictors",
        "clinvar",
        "exome",
        "genome",
    }
    compact = {k: v for k, v in raw.items() if k in keep}
    for source_key in ("exome", "genome"):
        if isinstance(compact.get(source_key), dict):
            compact[source_key] = project_variant_source(
                compact[source_key],
                select=populations,
                include_subcohorts=include_subcohorts,
                include_sex_split=include_sex_split,
                exclude_zero=exclude_zero_populations,
            )
    transcripts = compact.get("transcript_consequences")
    if isinstance(transcripts, list):
        # Stable sort: rank canonical/MANE first, then protein_coding, then
        # other biotypes; preserve original order within a rank tier.
        ranked = sorted(
            enumerate(transcripts),
            key=lambda item: (_rank_transcript(item[1]), item[0]),
        )
        ordered = [tx for _, tx in ranked]
        if len(ordered) > max_transcripts:
            dropped = len(ordered) - max_transcripts
            compact["transcript_consequences"] = ordered[:max_transcripts]
            compact["truncated"] = {
                "kind": "transcript_consequences",
                "dropped": dropped,
                "filter": {"max_transcripts": max_transcripts},
                "to_disable": "response_mode='full' returns every transcript",
                "to_restore": "response_mode='full'",
            }
        else:
            compact["transcript_consequences"] = ordered
    return compact


def shape_gene_details_compact(raw: dict[str, Any]) -> dict[str, Any]:
    """Project a Gene payload to constraint + canonical transcript + coordinates.

    Drops heavy arrays (transcripts, exons, alt_transcripts) and emits a
    truncated block so the LLM can request the full payload with
    response_mode='full'.
    """
    heavy_keys = {"transcripts", "exons", "alt_transcripts"}
    dropped: dict[str, int] = {}
    for k in heavy_keys:
        v = raw.get(k)
        if v:
            dropped[k] = len(v)
    compact = {k: v for k, v in raw.items() if k not in heavy_keys}
    if dropped:
        compact["truncated"] = {
            "kind": "gene_payload",
            "dropped": dropped,
            "to_disable": "response_mode='full' returns the full payload",
            "to_restore": "response_mode='full'",
        }
    return compact


def _classify_clinical_significance(sig: str | None) -> str:
    """Map a free-text ClinVar clinical_significance to a canonical bucket.

    Ordering matters: "uncertain" is checked first so "Uncertain significance"
    cannot fall through to the pathogenic/benign branches. "conflicting" is
    checked next so "Conflicting classifications of pathogenicity" is not
    swallowed by the bare "pathogenic" substring branch (mirrors the
    gene_carrier_filters P/LP rule, which excludes conflicting). Then "likely
    pathogenic" / "likely benign" win over their bare counterparts so the
    "likely" substring is not swallowed by a broader match.
    """
    if not sig:
        return "other"
    s = sig.lower()
    if "uncertain" in s or "vus" in s:
        return "uncertain"
    if "conflicting" in s:
        return "conflicting"
    if "pathogenic" in s and "likely" in s:
        return "likely_pathogenic"
    if "pathogenic" in s:
        return "pathogenic"
    if "benign" in s and "likely" in s:
        return "likely_benign"
    if "benign" in s:
        return "benign"
    return "other"


def summarize_clinvar_submissions(submissions: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate ClinVar submissions into pathogenic/benign/uncertain counts.

    Returns a dict with counts per classification bucket, a `conflict` flag
    (True when both pathogenic-side and benign-side reviewers are present),
    and total. Counts are computed from the FULL input, so a truncated
    response still reports accurate aggregates. "Conflicting classifications of
    pathogenicity" submissions land in their own `conflicting` bucket and do not
    inflate the pathogenic side.
    """
    counts = {
        "pathogenic": 0,
        "likely_pathogenic": 0,
        "uncertain": 0,
        "conflicting": 0,
        "likely_benign": 0,
        "benign": 0,
        "other": 0,
    }
    for s in submissions:
        counts[_classify_clinical_significance(s.get("clinical_significance"))] += 1
    pathogenic_side = counts["pathogenic"] + counts["likely_pathogenic"]
    benign_side = counts["benign"] + counts["likely_benign"]
    return {
        **counts,
        "conflict": pathogenic_side > 0 and benign_side > 0,
        "total": len(submissions),
    }


def shape_clinvar_submissions(payload: dict[str, Any], *, submissions_limit: int) -> dict[str, Any]:
    """Cap submissions[] and emit truncated metadata. Returns a copy of payload."""
    submissions = payload.get("submissions") or []
    if len(submissions) <= submissions_limit:
        return payload
    capped = dict(payload)
    capped["submissions"] = submissions[:submissions_limit]
    capped["truncated"] = {
        "kind": "submissions",
        "dropped": len(submissions) - submissions_limit,
        "filter": {"submissions_limit": submissions_limit},
        "to_disable": "raise submissions_limit (max 200)",
        "to_restore": f"submissions_limit={min(len(submissions), 200)}",
    }
    return capped


def cap_region_span(
    chrom: str, start: int, stop: int, *, max_bp: int = 100_000
) -> tuple[int, int, bool]:
    """Clamp a region request to `max_bp` and report whether truncation occurred."""

    span = stop - start
    if span <= max_bp:
        return start, stop, False
    return start, start + max_bp, True


_REGION_CLINVAR_KEEP = {
    "variant_id",
    "clinical_significance",
    "review_status",
    "gold_stars",
    "major_consequence",
    "consequence",
    "pos",
    "ref",
    "alt",
}

_REGION_GENE_KEEP = {
    "gene_id",
    "ensembl_id",
    "symbol",
    "chrom",
    "start",
    "stop",
    "strand",
    "biotype",
    "reference_genome",
}


def _project_row(row: dict[str, Any], keep: set[str]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k in keep}


def shape_region_payload(
    payload: dict[str, Any],
    *,
    include_clinvar: bool,
    include_genes: bool,
    max_clinvar_variants: int,
    max_genes: int,
    compact_rows: bool,
) -> dict[str, Any]:
    """Cap clinvar_variants[] and genes[] in a region payload.

    Optionally projects each row to a compact key set (drops heavy fields like
    `submissions` on ClinVar rows and `transcripts`/`exons` on gene rows).
    When any list is capped, emits a self-describing ``truncated_payload``
    block alongside the existing ``truncated`` span block (kept separate so
    callers that key off ``truncated.kind == "region_span"`` keep working).
    """

    out = dict(payload)
    dropped: dict[str, int] = {}

    if include_clinvar:
        rows = list(payload.get("clinvar_variants") or [])
        if compact_rows:
            rows = [_project_row(r, _REGION_CLINVAR_KEEP) for r in rows]
        if len(rows) > max_clinvar_variants:
            dropped["clinvar_variants"] = len(rows) - max_clinvar_variants
            rows = rows[:max_clinvar_variants]
        out["clinvar_variants"] = rows
    else:
        out.pop("clinvar_variants", None)

    if include_genes:
        rows = list(payload.get("genes") or [])
        if compact_rows:
            rows = [_project_row(r, _REGION_GENE_KEEP) for r in rows]
        if len(rows) > max_genes:
            dropped["genes"] = len(rows) - max_genes
            rows = rows[:max_genes]
        out["genes"] = rows
    else:
        out.pop("genes", None)

    if dropped:
        restore_clinvar = max_clinvar_variants + dropped.get("clinvar_variants", 0)
        restore_genes = max_genes + dropped.get("genes", 0)
        out["truncated_payload"] = {
            "kind": "region_payload",
            "dropped": dropped,
            "filter": {
                "max_clinvar_variants": max_clinvar_variants,
                "max_genes": max_genes,
                "compact_rows": compact_rows,
            },
            "to_disable": ("raise max_clinvar_variants / max_genes or set compact_rows=False"),
            "to_restore": (f"max_clinvar_variants={restore_clinvar}, max_genes={restore_genes}"),
        }

    return out
