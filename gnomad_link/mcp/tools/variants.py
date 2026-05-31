"""Variant tools: get_variant_frequencies, get_variant_details."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.build_check import detect_variant_id_mismatch
from gnomad_link.mcp.errors import BuildMismatchError, McpErrorContext, run_mcp_tool
from gnomad_link.mcp.headline import variant_frequencies_headline
from gnomad_link.mcp.minimal_shaping import project_variant_frequencies_minimal
from gnomad_link.mcp.next_commands import for_variant
from gnomad_link.mcp.schema_relax import relax_output_schema
from gnomad_link.mcp.shaping import (
    shape_variant_details_compact,
    shape_variant_frequencies,
)
from gnomad_link.models import VariantDetails
from gnomad_link.services import FrequencyService

# Autosomal CHROM-POS-REF-ALT grammar. Chromosomes 1-22, X, Y only; mito
# variants must go through get_mitochondrial_variant. Allele letters are upper
# case A/C/G/T (no N, no IUPAC ambiguity codes — gnomAD does not return those).
_AUTOSOMAL_VARIANT_ID_PATTERN = r"^([1-9]|1\d|2[0-2]|X|Y)-\d+-[ACGT]+-[ACGT]+$"

_FREQ_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "variant_id": {"type": "string"},
        "dataset": {"type": "string"},
        "gene_symbol": {"type": ["string", "null"]},
        "major_consequence": {"type": ["string", "null"]},
        "exome": {"type": ["object", "null"]},
        "genome": {"type": ["object", "null"]},
        "summary": {"type": ["object", "null"]},
    },
    "required": ["variant_id", "dataset"],
    "additionalProperties": True,
}


def register_variant_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="get_variant_frequencies",
        title="Get Variant Frequencies",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=relax_output_schema(_FREQ_OUTPUT_SCHEMA),
        tags={"variant"},
    )
    async def get_variant_frequencies(
        variant_id: Annotated[
            str,
            Field(
                description="CHROM-POS-REF-ALT (e.g. 1-55051215-G-GA). Use M-POS-REF-ALT only with get_mitochondrial_variant.",
                min_length=5,
                max_length=200,
                pattern=_AUTOSOMAL_VARIANT_ID_PATTERN,
                examples=["1-55051215-G-GA", "17-7674232-G-A"],
            ),
        ],
        dataset: Annotated[
            Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"],
            Field(
                description="gnomad_r4 (GRCh38, default, largest cohort), gnomad_r3 (GRCh38, whole-genome), gnomad_r2_1 (GRCh37 legacy)",
                examples=["gnomad_r4"],
            ),
        ] = "gnomad_r4",
        populations: Annotated[
            list[str] | None,
            Field(
                description="Restrict to these population codes (e.g. ['afr','nfe']). None returns all kept rows.",
                examples=[["afr", "nfe"]],
            ),
        ] = None,
        include_subcohorts: Annotated[
            bool,
            Field(description="Include non_topmed_*, non_ukb_*, 1kg_*, hgdp_*, controls_* rows."),
        ] = False,
        include_sex_split: Annotated[
            bool,
            Field(description="Include _XX/_XY sex-split rows."),
        ] = False,
        exclude_zero_populations: Annotated[
            bool,
            Field(description="Drop populations with allele_count == 0."),
        ] = True,
        response_mode: Annotated[
            Literal["compact", "full", "minimal"],
            Field(
                description=(
                    "compact (default) = today's behavior, honoring the "
                    "include_subcohorts/include_sex_split/exclude_zero_populations toggles. "
                    "full = most-inclusive population detail (subcohorts + sex-split + zero-AC "
                    "rows). minimal = headline + overall/max-pop summary + _meta only (drops the "
                    "exome/genome per-population arrays). response_mode='full' and "
                    "response_mode='minimal' take PRECEDENCE over the explicit toggles above."
                )
            ),
        ] = "compact",
    ) -> dict[str, Any]:
        """Use this when a caller has a fully-resolved CHROM-POS-REF-ALT id and needs allele counts/frequencies per population. Pair with get_clinvar_variant_details for clinical context. Compact defaults trim subcohort and zero-AC rows; toggle the boolean flags to expand, or use response_mode='full' for the most-inclusive breakdown or response_mode='minimal' for just the headline + overall/max-pop summary. Returns a `truncated` block when filters drop rows so the LLM can re-call with explicit overrides. Returns ~2-4kB (minimal ~0.6kB)."""

        async def call() -> dict[str, Any]:
            inferred = detect_variant_id_mismatch(variant_id, dataset)
            if inferred is not None:
                raise BuildMismatchError(
                    variant_id=variant_id, inferred_build=inferred, dataset=dataset
                )
            service = service_factory()
            response = await service.get_variant_frequencies(variant_id, dataset)
            # response_mode='full' takes precedence over the explicit toggles and
            # asks for the most-inclusive breakdown; compact/minimal honor them.
            if response_mode == "full":
                eff_subcohorts, eff_sex_split, eff_exclude_zero = True, True, False
            else:
                eff_subcohorts = include_subcohorts
                eff_sex_split = include_sex_split
                eff_exclude_zero = exclude_zero_populations
            shaped = shape_variant_frequencies(
                response,
                populations=populations,
                include_subcohorts=eff_subcohorts,
                include_sex_split=eff_sex_split,
                exclude_zero_populations=eff_exclude_zero,
            )
            # Lead with the plain-English headline so an LLM can answer fast.
            shaped = {"headline": variant_frequencies_headline(shaped), **shaped}
            # Suggest pairing with ClinVar for clinical annotation context.
            existing_meta: dict[str, Any] = shaped.get("_meta") or {}
            existing_next: list[Any] = existing_meta.get("next_commands", [])
            clinvar_cmd: dict[str, Any] = {
                "tool": "get_clinvar_variant_details",
                "arguments": {
                    "variant_id": variant_id,
                    "reference_genome": "GRCh37" if dataset == "gnomad_r2_1" else "GRCh38",
                },
            }
            shaped["_meta"] = {
                **existing_meta,
                "next_commands": [*existing_next, clinvar_cmd],
            }
            if response_mode == "minimal":
                return project_variant_frequencies_minimal(shaped)
            return shaped

        return await run_mcp_tool(
            "get_variant_frequencies",
            call,
            context=McpErrorContext(
                tool_name="get_variant_frequencies",
                variant_id=variant_id,
                dataset=dataset,
            ),
        )

    @mcp.tool(
        name="get_variant_details",
        title="Get Variant Details",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=relax_output_schema(VariantDetails.model_json_schema()),
        tags={"variant"},
    )
    async def get_variant_details(
        variant_id: Annotated[
            str,
            Field(
                description="CHROM-POS-REF-ALT id (e.g. 1-55051215-G-GA). "
                "Use get_mitochondrial_variant for M-POS-REF-ALT.",
                min_length=5,
                max_length=200,
                pattern=_AUTOSOMAL_VARIANT_ID_PATTERN,
                examples=["1-55051215-G-GA"],
            ),
        ],
        dataset: Annotated[
            Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"],
            Field(
                description="gnomad_r4 (GRCh38, default, largest cohort), gnomad_r3 (GRCh38, whole-genome), gnomad_r2_1 (GRCh37 legacy)",
                examples=["gnomad_r4"],
            ),
        ] = "gnomad_r4",
        response_mode: Annotated[
            Literal["compact", "full"],
            Field(
                description=(
                    "compact strips raw GraphQL extras and trims the population "
                    "breakdown (see the toggles below); full passes through everything."
                )
            ),
        ] = "compact",
        max_transcripts: Annotated[
            int,
            Field(ge=1, le=200, description="Cap on transcript_consequences in compact mode."),
        ] = 10,
        populations: Annotated[
            list[str] | None,
            Field(
                description="Restrict population rows to these codes (e.g. ['afr','nfe']). None keeps all kept rows.",
                examples=[["afr", "nfe"]],
            ),
        ] = None,
        include_subcohorts: Annotated[
            bool,
            Field(description="Include non_topmed_*, non_ukb_*, 1kg_*, hgdp_*, controls_* rows."),
        ] = False,
        include_sex_split: Annotated[
            bool,
            Field(description="Include _XX/_XY sex-split rows."),
        ] = False,
        exclude_zero_populations: Annotated[
            bool,
            Field(description="Drop populations with allele_count == 0 (compact mode)."),
        ] = True,
    ) -> dict[str, Any]:
        """Use this when a caller needs transcript consequences, in-silico predictors, or ClinVar annotation for a single variant id. Prefer get_variant_frequencies if only allele counts are needed; this tool returns the larger annotation payload. Compact trims the exome/genome population breakdown (drops subcohort, sex-split, and zero-AC rows; toggle the booleans to expand) and emits a `truncated` block per source. Returns compact ~3-6kB, full up to ~50kB."""

        async def call() -> dict[str, Any]:
            inferred = detect_variant_id_mismatch(variant_id, dataset)
            if inferred is not None:
                raise BuildMismatchError(
                    variant_id=variant_id, inferred_build=inferred, dataset=dataset
                )
            service = service_factory()
            raw = await service.get_variant(variant_id, dataset)
            # service.get_variant returns the GraphQL wrapper {"variant": {...}};
            # unwrap (like the SV/mito/region tools) before shaping. Guard against
            # a silent-empty success: an absent variant block is a not_found, not
            # a bare _meta payload.
            variant: dict[str, Any] = raw.get("variant", raw) if isinstance(raw, dict) else raw
            if not variant:
                from gnomad_link.api.base_client import VariantNotFoundError

                raise VariantNotFoundError(f"Variant {variant_id} not found in {dataset}")
            if response_mode == "compact":
                result = shape_variant_details_compact(
                    variant,
                    max_transcripts=max_transcripts,
                    populations=populations,
                    include_subcohorts=include_subcohorts,
                    include_sex_split=include_sex_split,
                    exclude_zero_populations=exclude_zero_populations,
                )
            else:
                result = variant
            # Standard follow-ups: per-population frequencies, then ClinVar.
            result.setdefault("_meta", {}).setdefault(
                "next_commands", for_variant(variant_id, dataset)
            )
            return result

        return await run_mcp_tool(
            "get_variant_details",
            call,
            context=McpErrorContext(
                tool_name="get_variant_details", variant_id=variant_id, dataset=dataset
            ),
        )
