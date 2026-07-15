"""Shared population-row projection for the variant-bearing MCP tools.

`get_variant_frequencies`, `get_variant_details`, and `get_gene_variants` all
return gnomAD population breakdowns. Left raw, those breakdowns are the single
largest token sink in the facade: a common variant carries 200+ rows once the
HGDP and 1kg subcohorts and the _XX/_XY sex splits are included, the vast
majority with ``ac == 0``.

This module owns one projector used by all three tools so their trimming
behaviour and ``truncated`` envelopes stay identical. It accepts either the
Pydantic ``PopulationFrequency`` model (frequency path) or a raw GraphQL dict
(variant-details / gene-variants path); ``get_pop_attr`` bridges the two.
"""

from __future__ import annotations

from typing import Any

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

# Per-source population projection: the fixed key-set kept for every row.
_KEPT_POP_KEYS = ("id", "ac", "an", "af", "homozygote_count")

POPULATIONS_TO_DISABLE = (
    "set include_subcohorts=True and include_sex_split=True and "
    "exclude_zero_populations=False for the full upstream payload"
)

_TO_RESTORE_MAPPING = {
    "subcohorts": "include_subcohorts=True",
    "sex_split": "include_sex_split=True",
    "zero_ac": "exclude_zero_populations=False",
    "not_selected": "populations=None (remove population filter)",
}


def _base_population(pop_id: str) -> str:
    """Strip a known subcohort prefix and/or an _XX/_XY sex suffix to the base ancestry."""
    base = pop_id
    for prefix in SUBCOHORT_PREFIXES:
        if base.startswith(prefix):
            base = base[len(prefix) :]
            break
    for suffix in ("_XX", "_XY"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return base


def validate_population_codes(populations: list[str] | None) -> None:
    """Reject an unrecognised population code instead of silently matching nothing.

    The ``populations`` filter is a CLOSED vocabulary (the gnomAD ancestry groups,
    optionally carrying a subcohort prefix and/or an _XX/_XY sex suffix). Left
    unvalidated, ``populations=['__bogus__']`` matches no row and returns
    ``success:true`` with an empty breakdown -- indistinguishable from "this
    variant has no data for that ancestry" (the silently-empty filter forbidden by
    Response-Envelope v1.1). Shared by every variant-bearing tool so the closed set
    and the rejection are identical across the surface.

    Declared as a runtime guard rather than a per-tool ``Literal`` so the ~10-value
    ancestry enum (times its subcohort/sex variants) is not multiplied across four
    tool schemas -- the message names the parameter and the valid set. Raises
    ``ToolInputError`` (-> ``invalid_input``) naming ``populations`` and the valid
    codes; never echoes the caller's value.
    """
    if not populations:
        return
    from gnomad_link.mcp.errors import ToolInputError

    for code in populations:
        if not isinstance(code, str):
            raise ToolInputError(
                "Each entry in 'populations' must be a population code string; valid "
                f"ancestry codes are {sorted(BASE_POPULATION_CODES)} (optionally with an "
                "_XX/_XY sex suffix or a subcohort prefix such as non_topmed_)."
            )
        if code in {"XX", "XY"}:
            continue
        if _base_population(code) not in BASE_POPULATION_CODES:
            raise ToolInputError(
                "Unrecognised value in 'populations'. Valid ancestry codes are "
                f"{sorted(BASE_POPULATION_CODES)} (optionally with an _XX/_XY sex suffix "
                "or a subcohort prefix such as non_topmed_/1kg_/hgdp_)."
            )


def is_subcohort(pop_id: str) -> bool:
    return pop_id.startswith(SUBCOHORT_PREFIXES)


def is_sex_split(pop_id: str) -> bool:
    return pop_id in {"XX", "XY"} or pop_id.endswith(("_XX", "_XY"))


def get_pop_attr(pop: Any, attr_name: str, dict_key: str, default: Any = None) -> Any:
    """Read a field from a Pydantic model or a dict, checking for None explicitly."""
    val = getattr(pop, attr_name, None)
    if val is not None:
        return val
    if isinstance(pop, dict):
        return pop.get(dict_key, default)
    return default


def filter_populations(
    populations: list[Any],
    *,
    select: list[str] | None,
    include_subcohorts: bool,
    include_sex_split: bool,
    exclude_zero: bool,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Project + filter population rows; return (kept, dropped-by-reason counts)."""
    dropped = {"zero_ac": 0, "subcohorts": 0, "sex_split": 0, "not_selected": 0}
    kept: list[dict[str, Any]] = []
    for pop in populations:
        pop_id = get_pop_attr(pop, "name", "id") or get_pop_attr(pop, "id", "name")
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
        if not include_subcohorts and is_subcohort(pop_id):
            dropped["subcohorts"] += 1
            continue
        if not include_sex_split and is_sex_split(pop_id):
            dropped["sex_split"] += 1
            continue
        if exclude_zero and ac == 0:
            dropped["zero_ac"] += 1
            continue
        af = (ac / an) if an else None
        kept.append({"id": pop_id, "ac": ac, "an": an, "af": af, "homozygote_count": hom})
    return kept, dropped


def to_restore_hint(dropped: dict[str, int]) -> str | None:
    """Return the most targeted parameter override to restore the largest dropped category."""
    best_key: str | None = None
    best_count = 0
    for key, count in dropped.items():
        if count > best_count:
            best_count = count
            best_key = key
    if best_key is None or best_count == 0:
        return None
    return _TO_RESTORE_MAPPING.get(best_key)


def build_populations_truncated(
    dropped: dict[str, int],
    *,
    select: list[str] | None,
    include_subcohorts: bool,
    include_sex_split: bool,
    exclude_zero: bool,
) -> dict[str, Any] | None:
    """Build the standard ``truncated.kind == "populations"`` block, or None if nothing dropped."""
    if sum(dropped.values()) == 0:
        return None
    truncated: dict[str, Any] = {
        "kind": "populations",
        "dropped": dropped,
        "filter": {
            "include_subcohorts": include_subcohorts,
            "include_sex_split": include_sex_split,
            "exclude_zero_populations": exclude_zero,
            "populations": select,
        },
        "to_disable": POPULATIONS_TO_DISABLE,
    }
    hint = to_restore_hint(dropped)
    if hint:
        truncated["to_restore"] = hint
    return truncated


# Source-level scalar keys carried through verbatim from a raw GraphQL exome/genome
# dict. ``filters`` is QC-relevant (e.g. AC0, RF) and must never be trimmed.
_SOURCE_SCALAR_KEYS = ("ac", "an", "af", "homozygote_count", "hemizygote_count", "filters")


def project_variant_source(
    source: Any,
    *,
    select: list[str] | None,
    include_subcohorts: bool,
    include_sex_split: bool,
    exclude_zero: bool,
    include_populations: bool = True,
    emit_truncated: bool = True,
) -> Any:
    """Project a raw GraphQL exome/genome dict: trim its population rows in place.

    Preserves source-level scalars (ac/an/af/homozygote_count/hemizygote_count/filters)
    and replaces ``populations`` with the trimmed projection, attaching a
    ``truncated`` block when rows are dropped. ``include_populations=False`` drops
    the population array entirely (keeping only source-level scalars) for callers
    that scan many variants and do not need the per-population breakdown.
    ``emit_truncated=False`` suppresses the per-source ``truncated`` block so a
    list caller (gene-variants) can report one aggregate projection note instead
    of one block per row.

    Non-dict input (e.g. ``None``) is returned unchanged so callers can pass an
    absent exome/genome straight through.
    """
    if not isinstance(source, dict):
        return source
    out: dict[str, Any] = {k: source[k] for k in _SOURCE_SCALAR_KEYS if k in source}
    if "af" not in out:
        ac = out.get("ac")
        an = out.get("an")
        out["af"] = (ac / an) if ac is not None and an else None
    raw_pops = source.get("populations") or []
    kept, dropped = filter_populations(
        raw_pops,
        select=select,
        include_subcohorts=include_subcohorts,
        include_sex_split=include_sex_split,
        exclude_zero=exclude_zero,
    )
    if include_populations:
        out["populations"] = kept
        if emit_truncated:
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


def population_projection_note(
    *,
    select: list[str] | None,
    include_subcohorts: bool,
    include_sex_split: bool,
    exclude_zero: bool,
    include_populations: bool,
) -> dict[str, Any]:
    """Describe the per-variant population projection applied by a list endpoint.

    A single payload-level note (vs one ``truncated`` block per row) telling the
    LLM what was trimmed from every variant's exome/genome populations and how to
    restore the full upstream breakdown.
    """
    return {
        "applied_to": "each variant's exome/genome populations",
        "filter": {
            "include_populations": include_populations,
            "include_subcohorts": include_subcohorts,
            "include_sex_split": include_sex_split,
            "exclude_zero_populations": exclude_zero,
            "populations": select,
        },
        "to_disable": (
            "set include_populations=True, include_subcohorts=True, "
            "include_sex_split=True, exclude_zero_populations=False for full per-variant rows"
        ),
        "to_restore": (
            "include_populations=True"
            if not include_populations
            else "exclude_zero_populations=False"
        ),
    }
