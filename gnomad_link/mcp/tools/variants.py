"""Variant tools: get_variant_frequencies, get_variant_details."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool
from gnomad_link.mcp.shaping import (
    shape_variant_details_compact,
    shape_variant_frequencies,
)
from gnomad_link.models import VariantDetails
from gnomad_link.services import FrequencyService

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
        output_schema=_FREQ_OUTPUT_SCHEMA,
    )
    async def get_variant_frequencies(
        variant_id: Annotated[
            str,
            Field(
                description="CHROM-POS-REF-ALT (e.g. 1-55051215-G-GA). Use M-POS-REF-ALT only with get_mitochondrial_variant.",
                min_length=5,
                max_length=200,
                pattern=r"^[^'\"]+$",
            ),
        ],
        dataset: Annotated[
            Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"],
            Field(description="Dataset. gnomad_r4 default (GRCh38)."),
        ] = "gnomad_r4",
        populations: Annotated[
            list[str] | None,
            Field(
                description="Restrict to these population codes (e.g. ['afr','nfe']). None returns all kept rows."
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
    ) -> dict[str, Any]:
        """Use this when a caller has a fully-resolved CHROM-POS-REF-ALT id and needs allele counts/frequencies per population. Pair with get_clinvar_variant_details for clinical context. Compact defaults trim subcohort and zero-AC rows; toggle the boolean flags to expand. Returns a `truncated` block when filters drop rows so the LLM can re-call with explicit overrides."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            response = await service.get_variant_frequencies(variant_id, dataset)
            return shape_variant_frequencies(
                response,
                populations=populations,
                include_subcohorts=include_subcohorts,
                include_sex_split=include_sex_split,
                exclude_zero_populations=exclude_zero_populations,
            )

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
        output_schema=VariantDetails.model_json_schema(),
    )
    async def get_variant_details(
        variant_id: Annotated[
            str,
            Field(min_length=5, max_length=200, pattern=r"^[^'\"]+$"),
        ],
        dataset: Annotated[Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"], Field()] = "gnomad_r4",
        response_mode: Annotated[
            Literal["compact", "full"],
            Field(description="compact strips raw GraphQL extras; full passes through everything."),
        ] = "compact",
    ) -> dict[str, Any]:
        """Use this when a caller needs transcript consequences, in-silico predictors, or ClinVar annotation for a single variant id. Prefer get_variant_frequencies if only allele counts are needed; this tool returns the larger annotation payload."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            raw = await service.get_variant(variant_id, dataset)
            if response_mode == "compact":
                return shape_variant_details_compact(raw)
            return raw

        return await run_mcp_tool(
            "get_variant_details",
            call,
            context=McpErrorContext(
                tool_name="get_variant_details", variant_id=variant_id, dataset=dataset
            ),
        )
