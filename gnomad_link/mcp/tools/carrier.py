"""Carrier-frequency tool: compute_carrier_frequency (pure local HWE math)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.build_check import detect_variant_id_mismatch
from gnomad_link.mcp.errors import BuildMismatchError, McpErrorContext, run_mcp_tool
from gnomad_link.mcp.schema_relax import relax_output_schema
from gnomad_link.models import VariantDataSource, VariantFrequencyResponse
from gnomad_link.services import FrequencyService
from gnomad_link.services.carrier_math import (
    ar_affected,
    ar_carrier,
    variant_carrier_rate,
    wilson_ci,
)

# Shared with get_variant_frequencies: autosomal CHROM-POS-REF-ALT grammar.
_AUTOSOMAL_VARIANT_ID_PATTERN = r"^([1-9]|1\d|2[0-2]|X|Y)-\d+-[ACGT]+-[ACGT]+$"

_CITATIONS = [
    "Schrodi et al. 2015, Hum Genet, doi:10.1007/s00439-015-1551-8 (2pq/q^2 carrier framework + CI concept)",
    "Karczewski et al. 2020, Nature (gnomAD allele-frequency reference)",
    "Guo et al. 2019; Zhu et al. 2022 (homozygote-corrected variant carrier rate)",
    "Hotakainen et al. 2025; Kandolin et al. 2024 (X-linked sex-split estimation)",
]

_ASSUMPTIONS_NOTE = (
    "Estimates assume Hardy-Weinberg equilibrium, random mating, complete "
    "penetrance, and a single causal variant. Frequencies are a minimum "
    "estimate from one gnomAD variant and are unsafe for clinical use."
)

_CARRIER_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "variant_id": {"type": "string"},
        "dataset": {"type": "string"},
        "inheritance": {"type": "string"},
        "method": {"type": "string"},
        "overall": {"type": ["object", "null"]},
        "per_population": {"type": "array", "items": {"type": "object"}},
        "summary": {"type": ["object", "null"]},
        "assumptions_note": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "string"}},
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
        if pop.allele_number <= 0:
            rows.append(
                {
                    "population": pop.name,
                    "ac": pop.allele_count,
                    "an": pop.allele_number,
                    "af": None,
                    "carrier_frequency": None,
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
        rows.append(
            {
                "population": pop.name,
                "ac": pop.allele_count,
                "an": pop.allele_number,
                "af": af,
                "carrier_frequency": cf,
                "affected_frequency": ar_affected(af),
            }
        )
    return rows


def _max_carrier_population(rows: list[dict[str, Any]]) -> str | None:
    scored = [r for r in rows if r.get("carrier_frequency") is not None]
    if not scored:
        return None
    return str(max(scored, key=lambda r: r["carrier_frequency"])["population"])


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
    ) -> dict[str, Any]:
        """Use this when a caller needs an estimated carrier/affected frequency derived from a single gnomAD allele frequency under Hardy-Weinberg assumptions for AR, AD, or X-linked inheritance. Pure local math on top of get_variant_frequencies; returns Wilson 95% CIs, per-population breakdown, and embedded citations. Estimates are research-use only, never clinical decision support. Returns ~2-4kB."""

        async def call() -> dict[str, Any]:
            inferred = detect_variant_id_mismatch(variant_id, dataset)
            if inferred is not None:
                raise BuildMismatchError(
                    variant_id=variant_id, inferred_build=inferred, dataset=dataset
                )
            service = service_factory()
            response = await service.get_variant_frequencies(variant_id, dataset)
            source = _preferred_source(response)
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
                "assumptions_note": _ASSUMPTIONS_NOTE,
                "citations": list(_CITATIONS),
            }
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
