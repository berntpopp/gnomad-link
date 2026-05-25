"""Liftover and region tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool
from gnomad_link.mcp.shaping import cap_region_span
from gnomad_link.models import LiftoverResponse, Region
from gnomad_link.services import FrequencyService

_REGION_PATTERN = r"^(chr)?([1-9]|1[0-9]|2[0-2]|X|Y|M|MT)-\d+-\d+$"


def register_coordinate_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="liftover_variant",
        title="Liftover Variant Between GRCh37 and GRCh38",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=LiftoverResponse.model_json_schema(),
    )
    async def liftover_variant(
        source_variant_id: Annotated[
            str,
            Field(description="Variant ID to convert (CHROM-POS-REF-ALT)."),
        ],
        reference_genome: Annotated[
            Literal["GRCh37", "GRCh38"],
            Field(description="Reference build of source_variant_id."),
        ],
    ) -> dict[str, Any]:
        """Use this when a caller has a variant id in one reference build and needs the equivalent id in the other. Use this BEFORE calling frequency tools if the dataset and coordinate build do not match."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            results = await service.liftover_variant(source_variant_id, reference_genome)
            return {
                "results": results,
                "source_variant_id": source_variant_id,
                "source_reference_genome": reference_genome,
            }

        return await run_mcp_tool(
            "liftover_variant",
            call,
            context=McpErrorContext(tool_name="liftover_variant", variant_id=source_variant_id),
        )

    @mcp.tool(
        name="get_region",
        title="Get Variants and Genes in a Region",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=Region.model_json_schema(),
    )
    async def get_region(
        region: Annotated[
            str,
            Field(
                description="Region in chr-start-stop format (e.g. 17-7674232-7674252).",
                pattern=_REGION_PATTERN,
            ),
        ],
        dataset: Annotated[Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"], Field()] = "gnomad_r4",
        include_clinvar: Annotated[
            bool,
            Field(description="Include ClinVar variants in the region."),
        ] = True,
        include_genes: Annotated[
            bool,
            Field(description="Include overlapping genes."),
        ] = True,
    ) -> dict[str, Any]:
        """Use this when a caller wants genes and/or ClinVar variants in a small region (<=100kb). Spans larger than 100kb are clamped and a `truncated` block reports it. For per-variant SNV listings use get_gene_variants instead."""

        async def call() -> dict[str, Any]:
            chrom, start_s, stop_s = region.removeprefix("chr").split("-")
            start, stop = int(start_s), int(stop_s)
            if stop <= start:
                raise ValueError("Region stop must be greater than start.")
            adj_start, adj_stop, capped = cap_region_span(chrom, start, stop)
            service = service_factory()
            raw = await service.get_region(chrom, adj_start, adj_stop, dataset)
            payload = raw.get("region", raw) if isinstance(raw, dict) else raw
            if isinstance(payload, dict):
                if not include_clinvar:
                    payload.pop("clinvar_variants", None)
                if not include_genes:
                    payload.pop("genes", None)
                if capped:
                    payload["truncated"] = {
                        "kind": "region_span",
                        "requested_bp": stop - start,
                        "served_bp": adj_stop - adj_start,
                        "to_disable": "request smaller windows; max 100kb per call",
                    }
            return payload

        return await run_mcp_tool(
            "get_region",
            call,
            context=McpErrorContext(tool_name="get_region", region=region, dataset=dataset),
        )
