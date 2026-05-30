"""Carrier-frequency tool: compute_carrier_frequency (pure local HWE math)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.build_check import detect_variant_id_mismatch
from gnomad_link.mcp.errors import BuildMismatchError, McpErrorContext, run_mcp_tool
from gnomad_link.mcp.headline import variant_carrier_headline
from gnomad_link.mcp.provenance import provenance_block
from gnomad_link.mcp.schema_relax import relax_output_schema
from gnomad_link.models import PopulationFrequency, VariantDataSource, VariantFrequencyResponse
from gnomad_link.services import FrequencyService
from gnomad_link.services.carrier_math import (
    ad_affected_or_carrier,
    ar_affected,
    ar_carrier,
    variant_carrier_rate,
    wilson_ci,
    xl_affected_female,
    xl_affected_male,
    xl_female_carrier,
)

# Shared with get_variant_frequencies: autosomal CHROM-POS-REF-ALT grammar.
_AUTOSOMAL_VARIANT_ID_PATTERN = r"^([1-9]|1\d|2[0-2]|X|Y)-\d+-[ACGT]+-[ACGT]+$"

_CARRIER_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "variant_id": {"type": "string"},
        "dataset": {"type": "string"},
        "inheritance": {"type": "string"},
        "method": {"type": "string"},
        "overall": {"type": ["object", "null"]},
        "per_population": {"type": "array", "items": {"type": "object"}},
        "summary": {"type": ["object", "null"]},
        "assumptions_note": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "string"}},
        "citations_ref": {"type": "string"},
    },
    "required": ["variant_id", "dataset", "inheritance", "method"],
    "additionalProperties": True,
}


def _preferred_source(response: VariantFrequencyResponse) -> VariantDataSource | None:
    """Prefer exome (larger autosomal cohort), fall back to genome."""
    if response.exome is not None and response.exome.populations:
        return response.exome
    if response.genome is not None and response.genome.populations:
        return response.genome
    return response.exome or response.genome


def _is_sex_split_population(pop_name: str) -> bool:
    """True for sex-split pseudo-population rows (XX, XY, <anc>_XX, <anc>_XY).

    These are meaningful only for X-linked inheritance; for autosomal AR/AD they
    are noise (an autosomal variant has the same frequency in XX and XY) and must
    not appear in per-population rows or win the max-population pick.
    """
    return pop_name in ("XX", "XY") or pop_name.endswith(("_XX", "_XY"))


def _ar_overall(source: VariantDataSource | None, method: str) -> dict[str, Any]:
    if source is None or source.an <= 0:
        return {
            "af": None,
            "carrier_frequency": None,
            "ci_low": None,
            "ci_high": None,
            "affected_frequency": None,
        }
    af = source.ac / source.an
    if method == "hom_corrected":
        cf = variant_carrier_rate(
            ac=source.ac, homozygote_count=source.homozygote_count, an=source.an
        )
    else:
        cf = ar_carrier(af)
    ci_low, ci_high = wilson_ci(af=af, n=source.an)
    return {
        "af": af,
        "carrier_frequency": cf,
        "ci_low": ar_carrier(ci_low) if ci_low is not None else None,
        "ci_high": ar_carrier(ci_high) if ci_high is not None else None,
        "affected_frequency": ar_affected(af),
    }


def _ar_per_population(source: VariantDataSource | None, method: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if source is None:
        return rows
    for pop in source.populations:
        if _is_sex_split_population(pop.name):
            continue  # XL-only rows; meaningless for autosomal AR
        if pop.allele_number <= 0:
            rows.append(
                {
                    "population": pop.name,
                    "ac": pop.allele_count,
                    "an": pop.allele_number,
                    "af": None,
                    "carrier_frequency": None,
                    "ci_low": None,
                    "ci_high": None,
                    "affected_frequency": None,
                }
            )
            continue
        af = pop.allele_count / pop.allele_number
        if method == "hom_corrected":
            cf = variant_carrier_rate(
                ac=pop.allele_count,
                homozygote_count=pop.homozygote_count,
                an=pop.allele_number,
            )
        else:
            cf = ar_carrier(af)
        # Wilson CI on AF, mapped through the carrier transform, for parity with overall.
        ci_low, ci_high = wilson_ci(af=af, n=pop.allele_number)
        rows.append(
            {
                "population": pop.name,
                "ac": pop.allele_count,
                "an": pop.allele_number,
                "af": af,
                "carrier_frequency": cf,
                "ci_low": ar_carrier(ci_low) if ci_low is not None else None,
                "ci_high": ar_carrier(ci_high) if ci_high is not None else None,
                "affected_frequency": ar_affected(af),
            }
        )
    return rows


def _max_carrier_population(rows: list[dict[str, Any]]) -> str | None:
    def _score(row: dict[str, Any]) -> float | None:
        for key in ("carrier_frequency", "female_carrier_frequency"):
            value = row.get(key)
            if value is not None:
                return float(value)
        return None

    scored: list[tuple[dict[str, Any], float]] = [
        (row, s) for row in rows for s in (_score(row),) if s is not None
    ]
    if not scored:
        return None
    return str(max(scored, key=lambda item: item[1])[0]["population"])


def _ad_overall(source: VariantDataSource | None) -> dict[str, Any]:
    if source is None or source.an <= 0:
        return {
            "af": None,
            "affected_or_carrier_frequency": None,
            "ci_low": None,
            "ci_high": None,
        }
    af = source.ac / source.an
    ci_low, ci_high = wilson_ci(af=af, n=source.an)
    return {
        "af": af,
        "affected_or_carrier_frequency": ad_affected_or_carrier(af),
        "ci_low": ad_affected_or_carrier(ci_low) if ci_low is not None else None,
        "ci_high": ad_affected_or_carrier(ci_high) if ci_high is not None else None,
    }


def _ad_per_population(source: VariantDataSource | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if source is None:
        return rows
    for pop in source.populations:
        if _is_sex_split_population(pop.name):
            continue  # XL-only rows; meaningless for autosomal AD
        af = pop.allele_frequency
        ci_low: float | None = None
        ci_high: float | None = None
        if af is not None and pop.allele_number > 0:
            wl, wh = wilson_ci(af=af, n=pop.allele_number)
            ci_low = ad_affected_or_carrier(wl) if wl is not None else None
            ci_high = ad_affected_or_carrier(wh) if wh is not None else None
        rows.append(
            {
                "population": pop.name,
                "ac": pop.allele_count,
                "an": pop.allele_number,
                "af": af,
                "affected_or_carrier_frequency": (
                    ad_affected_or_carrier(af) if af is not None else None
                ),
                "carrier_frequency": ad_affected_or_carrier(af) if af is not None else None,
                "ci_low": ci_low,
                "ci_high": ci_high,
            }
        )
    return rows


def _sex_af(populations: list[PopulationFrequency], pop_id: str) -> float | None:
    for pop in populations:
        if pop.name == pop_id:
            return pop.allele_frequency
    return None


def _xl_block(q_xx: float | None, q_xy: float | None) -> dict[str, Any]:
    return {
        "q_xx": q_xx,
        "q_xy": q_xy,
        "female_carrier_frequency": xl_female_carrier(q_xx) if q_xx is not None else None,
        "affected_female_frequency": xl_affected_female(q_xx) if q_xx is not None else None,
        "affected_male_frequency": xl_affected_male(q_xy) if q_xy is not None else None,
    }


def _xl_ancestries(populations: list[PopulationFrequency]) -> list[str]:
    # Ancestry codes that carry sex-split rows like "<anc>_XX" / "<anc>_XY".
    ancestries: list[str] = []
    seen: set[str] = set()
    for pop in populations:
        name = pop.name
        if name in ("XX", "XY"):
            continue
        if name.endswith("_XX") or name.endswith("_XY"):
            anc = name.rsplit("_", 1)[0]
            if anc not in seen:
                seen.add(anc)
                ancestries.append(anc)
    return ancestries


def _xl_overall(source: VariantDataSource | None) -> dict[str, Any]:
    if source is None:
        return _xl_block(None, None)
    return _xl_block(
        _sex_af(source.populations, "XX"),
        _sex_af(source.populations, "XY"),
    )


def _xl_per_population(source: VariantDataSource | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if source is None:
        return rows
    for anc in _xl_ancestries(source.populations):
        q_xx = _sex_af(source.populations, f"{anc}_XX")
        q_xy = _sex_af(source.populations, f"{anc}_XY")
        block = _xl_block(q_xx, q_xy)
        rows.append(
            {
                "population": anc,
                "af_xx": q_xx,
                "af_xy": q_xy,
                "female_carrier_frequency": block["female_carrier_frequency"],
                "affected_female_frequency": block["affected_female_frequency"],
                "affected_male_frequency": block["affected_male_frequency"],
            }
        )
    return rows


def register_carrier_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="compute_carrier_frequency",
        title="Compute Carrier Frequency",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=relax_output_schema(_CARRIER_OUTPUT_SCHEMA),
        tags={"variant"},
    )
    async def compute_carrier_frequency(
        variant_id: Annotated[
            str,
            Field(
                description="CHROM-POS-REF-ALT (e.g. 7-117559590-ATCT-A). Autosomal/X-Y only.",
                min_length=5,
                max_length=200,
                pattern=_AUTOSOMAL_VARIANT_ID_PATTERN,
                examples=["7-117559590-ATCT-A", "X-153296777-C-T"],
            ),
        ],
        inheritance: Annotated[
            Literal["AR", "AD", "XL"],
            Field(
                description="AR=autosomal-recessive (2pq carrier, q^2 affected); AD=autosomal-dominant (1-(1-q)^2); XL=X-linked (sex-split).",
                examples=["AR"],
            ),
        ],
        dataset: Annotated[
            Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"],
            Field(
                description="gnomad_r4 (GRCh38, default, largest cohort), gnomad_r3 (GRCh38), gnomad_r2_1 (GRCh37 legacy)",
                examples=["gnomad_r4"],
            ),
        ] = "gnomad_r4",
        populations: Annotated[
            list[str] | None,
            Field(
                description="Restrict per_population rows to these population codes (e.g. ['afr','nfe']). None returns all.",
                examples=[["afr", "nfe"]],
            ),
        ] = None,
        method: Annotated[
            Literal["hwe", "hom_corrected"],
            Field(
                description="hwe = 2pq from AF; hom_corrected = (ac - 2*hom)/(an/2) observed variant carrier rate.",
                examples=["hwe"],
            ),
        ] = "hwe",
        response_mode: Annotated[
            Literal["compact", "full"],
            Field(
                description="compact (default) returns short citations + a citations_ref pointer "
                "to gnomad://citations; full inlines the complete bibliographic citations and "
                "assumptions prose."
            ),
        ] = "compact",
    ) -> dict[str, Any]:
        """Use this when a caller needs an estimated carrier/affected frequency derived from a single gnomAD allele frequency under Hardy-Weinberg assumptions for AR, AD, or X-linked inheritance. Pure local math on top of get_variant_frequencies; returns a one-line `headline`, Wilson 95% CIs, per-population breakdown, and provenance (short citations + a gnomad://citations pointer in compact mode; full citations with response_mode='full'). Estimates are research-use only, never clinical decision support. Returns ~2-4kB."""

        async def call() -> dict[str, Any]:
            inferred = detect_variant_id_mismatch(variant_id, dataset)
            if inferred is not None:
                raise BuildMismatchError(
                    variant_id=variant_id, inferred_build=inferred, dataset=dataset
                )
            service = service_factory()
            response = await service.get_variant_frequencies(variant_id, dataset)
            source = _preferred_source(response)
            if inheritance == "AD":
                overall = _ad_overall(source)
                per_population = _ad_per_population(source)
            elif inheritance == "XL":
                overall = _xl_overall(source)
                per_population = _xl_per_population(source)
            else:  # AR
                overall = _ar_overall(source, method)
                per_population = _ar_per_population(source, method)
            if populations is not None:
                wanted = {p.lower() for p in populations}
                per_population = [
                    row for row in per_population if row["population"].lower() in wanted
                ]
            result: dict[str, Any] = {
                "variant_id": variant_id,
                "dataset": dataset,
                "inheritance": inheritance,
                "method": method,
                "overall": overall,
                "per_population": per_population,
                "summary": {
                    "max_carrier_frequency_population": _max_carrier_population(per_population)
                },
                **provenance_block("variant_carrier", full=response_mode == "full"),
            }
            # Lead with the plain-English headline so an LLM can answer fast.
            result = {"headline": variant_carrier_headline(result), **result}
            reference_genome = "GRCh37" if dataset == "gnomad_r2_1" else "GRCh38"
            result["_meta"] = {
                "next_commands": [
                    {
                        "tool": "get_clinvar_variant_details",
                        "arguments": {
                            "variant_id": variant_id,
                            "reference_genome": reference_genome,
                        },
                    },
                    {
                        "tool": "get_variant_frequencies",
                        "arguments": {"variant_id": variant_id, "dataset": dataset},
                    },
                ]
            }
            return result

        return await run_mcp_tool(
            "compute_carrier_frequency",
            call,
            context=McpErrorContext(
                tool_name="compute_carrier_frequency",
                variant_id=variant_id,
                dataset=dataset,
            ),
        )
