"""Pure helpers that project gnomAD service responses into MCP-compact shapes."""

from __future__ import annotations

from typing import Any

from gnomad_link.models import VariantFrequencyResponse

BASE_POPULATION_CODES = {
    "afr",
    "amr",
    "asj",
    "eas",
    "fin",
    "nfe",
    "sas",
    "mid",
    "ami",
    "remaining",
}

SUBCOHORT_PREFIXES = (
    "non_topmed_",
    "non_ukb_",
    "non_v2_",
    "1kg_",
    "hgdp_",
    "controls_",
    "1kg:",
    "hgdp:",
)


def _is_subcohort(pop_id: str) -> bool:
    return pop_id.startswith(SUBCOHORT_PREFIXES)


def _is_sex_split(pop_id: str) -> bool:
    return pop_id in {"XX", "XY"} or pop_id.endswith(("_XX", "_XY"))


def _get_pop_attr(pop: Any, attr_name: str, dict_key: str, default: Any = None) -> Any:
    """Read a field from a Pydantic model or a dict, checking for None explicitly."""
    val = getattr(pop, attr_name, None)
    if val is not None:
        return val
    if isinstance(pop, dict):
        return pop.get(dict_key, default)
    return default


def _filter_populations(
    populations: list[Any],
    *,
    select: list[str] | None,
    include_subcohorts: bool,
    include_sex_split: bool,
    exclude_zero: bool,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    dropped = {"zero_ac": 0, "subcohorts": 0, "sex_split": 0, "not_selected": 0}
    kept: list[dict[str, Any]] = []
    for pop in populations:
        pop_id = _get_pop_attr(pop, "name", "id") or _get_pop_attr(pop, "id", "name")
        ac_raw = getattr(pop, "allele_count", None)
        ac = ac_raw if ac_raw is not None else (pop.get("ac", 0) if isinstance(pop, dict) else 0)
        an_raw = getattr(pop, "allele_number", None)
        an = an_raw if an_raw is not None else (pop.get("an", 0) if isinstance(pop, dict) else 0)
        hom_raw = getattr(pop, "homozygote_count", None)
        hom = (
            hom_raw
            if hom_raw is not None
            else (pop.get("homozygote_count", 0) if isinstance(pop, dict) else 0)
        )
        if select is not None and pop_id not in select:
            dropped["not_selected"] += 1
            continue
        if not include_subcohorts and _is_subcohort(pop_id):
            dropped["subcohorts"] += 1
            continue
        if not include_sex_split and _is_sex_split(pop_id):
            dropped["sex_split"] += 1
            continue
        if exclude_zero and ac == 0:
            dropped["zero_ac"] += 1
            continue
        af = (ac / an) if an else None
        kept.append({"id": pop_id, "ac": ac, "an": an, "af": af, "homozygote_count": hom})
    return kept, dropped


def _to_restore_hint(dropped: dict[str, int]) -> str | None:
    """Return the most targeted parameter override to restore the largest dropped category."""
    best_key: str | None = None
    best_count = 0
    for key, count in dropped.items():
        if count > best_count:
            best_count = count
            best_key = key
    if best_key is None or best_count == 0:
        return None
    mapping = {
        "subcohorts": "include_subcohorts=True",
        "sex_split": "include_sex_split=True",
        "zero_ac": "exclude_zero_populations=False",
        "not_selected": "populations=None (remove population filter)",
    }
    return mapping.get(best_key)


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
    populations, dropped = _filter_populations(
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
    total_dropped = sum(dropped.values())
    if total_dropped:
        to_restore = _to_restore_hint(dropped)
        truncated: dict[str, Any] = {
            "kind": "populations",
            "dropped": dropped,
            "filter": {
                "include_subcohorts": include_subcohorts,
                "include_sex_split": include_sex_split,
                "exclude_zero_populations": exclude_zero,
                "populations": select,
            },
            "to_disable": (
                "set include_subcohorts=True and include_sex_split=True and "
                "exclude_zero_populations=False for the full upstream payload"
            ),
        }
        if to_restore:
            truncated["to_restore"] = to_restore
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


def shape_gene_variants(
    raw: list[dict[str, Any]],
    *,
    limit: int,
    consequence: str | None,
    max_af: float | None,
    min_ac: int | None,
) -> dict[str, Any]:
    """Filter and cap a gene-variants list. Always returns a `truncated` block when the cap fires."""

    if limit <= 0 or limit > 500:
        raise ValueError("limit must be in [1, 500]")
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
        filtered.append(v)
        if len(filtered) >= limit:
            break
    payload = {"variants": filtered, "returned": len(filtered), "total_seen": total_seen}
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
    raw: dict[str, Any], *, max_transcripts: int = 10
) -> dict[str, Any]:
    """Project the gnomAD variant payload to the compact subset advertised in VariantDetails.

    Caps ``transcript_consequences`` at ``max_transcripts`` entries and emits a
    self-describing ``truncated`` block so the LLM can request the full payload
    with ``response_mode='full'``. Within the cap, canonical / MANE-Select
    transcripts win the slots first, then ``protein_coding`` entries, then the
    rest; original order is preserved within each rank tier.
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
