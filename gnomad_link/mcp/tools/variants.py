"""Variant tools: get_variant_frequencies, get_variant_details."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.api import DataNotFoundError
from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.build_check import detect_variant_id_mismatch
from gnomad_link.mcp.errors import BuildMismatchError, McpErrorContext, run_mcp_tool
from gnomad_link.mcp.headline import variant_frequencies_headline
from gnomad_link.mcp.minimal_shaping import project_variant_frequencies_minimal
from gnomad_link.mcp.next_commands import for_variant
from gnomad_link.mcp.other_build import not_found_with_other_build
from gnomad_link.mcp.patterns import hide_pattern
from gnomad_link.mcp.population_shaping import validate_population_codes
from gnomad_link.mcp.rsid import RSID_PATTERN, resolve_rsid
from gnomad_link.mcp.shaping import (
    shape_variant_details_compact,
    shape_variant_frequencies,
)
from gnomad_link.services import FrequencyService

# Autosomal CHROM-POS-REF-ALT grammar. Chromosomes 1-22, X, Y only; mito
# variants must go through get_mitochondrial_variant. Allele letters are upper
# case A/C/G/T (no N, no IUPAC ambiguity codes — gnomAD does not return those).
_AUTOSOMAL_VARIANT_ID_PATTERN = r"^([1-9]|1\d|2[0-2]|X|Y)-\d+-[ACGT]+-[ACGT]+$"
# Same grammar, or a dbSNP rsID resolved in-tool via the resolve_variant_id lookup.
_VARIANT_ID_OR_RSID_PATTERN = rf"^({_AUTOSOMAL_VARIANT_ID_PATTERN[1:-1]}|{RSID_PATTERN})$"


def register_variant_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="get_variant_frequencies",
        title="Get Variant Frequencies",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=None,
        tags={"variant"},
    )
    async def get_variant_frequencies(
        variant_id: Annotated[
            str,
            Field(
                description="CHROM-POS-REF-ALT (e.g. 1-55051215-G-GA) or an rsID. Use M-POS-REF-ALT only with get_mitochondrial_variant.",
                min_length=5,
                max_length=200,
                pattern=_VARIANT_ID_OR_RSID_PATTERN,
                json_schema_extra=hide_pattern,
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
        """Use this when a caller has a CHROM-POS-REF-ALT id or rsID; returns a headline, exome/genome AC/AN/AF per population, and a summary (max_pop_af, faf95). Pair with get_clinvar_variant_details for clinical context. Compact defaults trim subcohort and zero-AC rows; toggle the boolean flags to expand, or use response_mode='full' for the most-inclusive breakdown or response_mode='minimal' for just the headline + overall/max-pop summary. summary.max_pop_af is the raw highest-AF ancestry group (may be bottlenecked asj/fin; never 'remaining') and is NOT the filtering AF: use summary.faf95.{exome,genome,joint}.grpmax (gnomAD faf95 at grpmax, continental groups only; kept in minimal mode; a source is omitted when gnomAD computed no faf95 for it, e.g. AC 0 there) as the ClinGen/Whiffin comparator. A `truncated` block reports rows dropped by filters. Returns ~2-4kB (minimal ~0.6kB)."""

        ctx = McpErrorContext(
            tool_name="get_variant_frequencies", variant_id=variant_id, dataset=dataset
        )

        async def call() -> dict[str, Any]:
            validate_population_codes(populations)
            service = service_factory()
            vid, resolved_from = await resolve_rsid(
                service, variant_id, dataset, tool="get_variant_frequencies"
            )
            ctx.variant_id = vid
            inferred = detect_variant_id_mismatch(vid, dataset)
            if inferred is not None:
                raise BuildMismatchError(variant_id=vid, inferred_build=inferred, dataset=dataset)
            try:
                response = await service.get_variant_frequencies(vid, dataset)
            except DataNotFoundError as exc:
                raise await not_found_with_other_build(service, exc, ctx) from exc
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
                    "variant_id": vid,
                    "reference_genome": "GRCh37" if dataset == "gnomad_r2_1" else "GRCh38",
                },
            }
            shaped["_meta"] = {
                **existing_meta,
                "next_commands": [*existing_next, clinvar_cmd],
            }
            if response_mode == "minimal":
                shaped = project_variant_frequencies_minimal(shaped)
            if resolved_from:
                shaped["resolved_from"] = resolved_from
            return shaped

        return await run_mcp_tool("get_variant_frequencies", call, context=ctx)

    @mcp.tool(
        name="get_variant_details",
        title="Get Variant Details",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=None,
        tags={"variant"},
    )
    async def get_variant_details(
        variant_id: Annotated[
            str,
            Field(
                description="CHROM-POS-REF-ALT id (e.g. 1-55051215-G-GA) or an rsID. "
                "Use get_mitochondrial_variant for M-POS-REF-ALT.",
                min_length=5,
                max_length=200,
                pattern=_VARIANT_ID_OR_RSID_PATTERN,
                json_schema_extra=hide_pattern,
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
        """Use this when a caller has a single variant id; returns transcript consequences, in-silico predictors, and exome/genome frequencies. This tool does NOT return ClinVar clinical significance — for that call get_clinvar_variant_details. Prefer get_variant_frequencies if only allele counts are needed. Compact trims the exome/genome population breakdown (drops subcohort, sex-split, and zero-AC rows; toggle the booleans to expand) and emits a `truncated` block per source. Returns compact ~3-6kB, full up to ~50kB."""

        ctx = McpErrorContext(
            tool_name="get_variant_details", variant_id=variant_id, dataset=dataset
        )

        async def call() -> dict[str, Any]:
            validate_population_codes(populations)
            service = service_factory()
            vid, resolved_from = await resolve_rsid(
                service, variant_id, dataset, tool="get_variant_details"
            )
            ctx.variant_id = vid
            inferred = detect_variant_id_mismatch(vid, dataset)
            if inferred is not None:
                raise BuildMismatchError(variant_id=vid, inferred_build=inferred, dataset=dataset)
            raw = await service.get_variant(vid, dataset)
            # service.get_variant returns the GraphQL wrapper {"variant": {...}};
            # unwrap (like the SV/mito/region tools) before shaping. Guard against
            # a silent-empty success: an absent variant block is a not_found, not
            # a bare _meta payload.
            variant: dict[str, Any] = raw.get("variant", raw) if isinstance(raw, dict) else raw
            if not variant:
                from gnomad_link.api.base_client import VariantNotFoundError

                raise VariantNotFoundError(f"Variant {vid} not found in {dataset}")
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
            result.setdefault("_meta", {}).setdefault("next_commands", for_variant(vid, dataset))
            if resolved_from:
                result["resolved_from"] = resolved_from
            return result

        return await run_mcp_tool("get_variant_details", call, context=ctx)
