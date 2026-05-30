"""Structural-variant search tool: search_structural_variants."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.errors import McpErrorContext, ToolInputError, run_mcp_tool
from gnomad_link.mcp.schema_relax import relax_output_schema
from gnomad_link.mcp.sv_shaping import shape_sv_search
from gnomad_link.services import FrequencyService

# Cap how many returned ids become next_commands (no self-reference; <=3).
_NEXT_COMMAND_CAP = 3

_SV_SEARCH_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "object"},
        "returned": {"type": "integer"},
        "total_seen": {"type": "integer"},
        "structural_variants": {"type": "array", "items": {"type": "object"}},
        "truncated": {"type": ["object", "null"]},
    },
    "required": ["query", "returned", "total_seen", "structural_variants"],
    "additionalProperties": True,
}


def register_sv_search_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="search_structural_variants",
        title="Search Structural Variants in a Gene or Region",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=relax_output_schema(_SV_SEARCH_OUTPUT_SCHEMA),
        tags={"variant", "search"},
    )
    async def search_structural_variants(
        gene_symbol: Annotated[
            str | None,
            Field(
                description="HGNC gene symbol. Provide exactly one of gene_symbol, gene_id, or region.",
                examples=["SMARCA4"],
            ),
        ] = None,
        gene_id: Annotated[
            str | None,
            Field(
                description="Ensembl gene ID (preferred over symbol).",
                examples=["ENSG00000127616"],
            ),
        ] = None,
        region: Annotated[
            str | None,
            Field(
                description="Region in CHROM-START-STOP format (e.g. 19-11089000-11200000).",
                examples=["19-11089000-11200000"],
            ),
        ] = None,
        sv_dataset: Annotated[
            Literal["gnomad_sv_r4", "gnomad_sv_r2_1"],
            Field(
                description=(
                    "Structural-variant dataset (DISTINCT from SNV datasets). "
                    "gnomad_sv_r4 (GRCh38, default), gnomad_sv_r2_1 (GRCh37)."
                ),
                examples=["gnomad_sv_r4"],
            ),
        ] = "gnomad_sv_r4",
        sv_type: Annotated[
            str | None,
            Field(
                description="Filter by SV class (case-insensitive). One of "
                "DEL, DUP, INS, INV, BND, CPX, CTX, MCNV.",
                examples=["DEL"],
            ),
        ] = None,
        min_length: Annotated[
            int | None,
            Field(ge=0, description="Drop SVs shorter than this length (bp)."),
        ] = None,
        max_length: Annotated[
            int | None,
            Field(ge=0, description="Drop SVs longer than this length (bp)."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=500, description="Max SV rows returned (hard cap 500)."),
        ] = 100,
        response_mode: Annotated[
            Literal["compact", "full"],
            Field(description="compact projects each row to a fixed key-set; full is reserved."),
        ] = "compact",
    ) -> dict[str, Any]:
        """Use this when a caller wants the list of structural variants overlapping a gene or region. Provide exactly one of gene_symbol, gene_id, or region. SV variant_id values are OPAQUE (e.g. DEL_19_1), NOT CHROM-POS-REF-ALT, so no SNV id grammar is applied; fetch a single SV by id with get_structural_variant. sv_dataset is the DISTINCT structural-variant dataset enum (gnomad_sv_r4=GRCh38 default, gnomad_sv_r2_1=GRCh37), not the SNV dataset. Type/length filters are applied client-side. An empty match is a success with returned=0, not an error. Returns ~3-30kB (limit-dependent)."""

        async def call() -> dict[str, Any]:
            provided = [v for v in (gene_symbol, gene_id, region) if v]
            if len(provided) != 1:
                raise ToolInputError("Provide exactly one of gene_symbol, gene_id, or region.")
            service = service_factory()
            raw = await service.search_structural_variants(
                gene_symbol=gene_symbol,
                gene_id=gene_id,
                region=region,
                sv_dataset=sv_dataset,
            )
            shaped = shape_sv_search(
                raw,
                sv_type=sv_type,
                min_length=min_length,
                max_length=max_length,
                limit=limit,
            )
            query_echo: dict[str, Any] = {"sv_dataset": sv_dataset}
            if gene_id:
                query_echo = {"gene_id": gene_id, "sv_dataset": sv_dataset}
            elif gene_symbol:
                query_echo = {"gene_symbol": gene_symbol, "sv_dataset": sv_dataset}
            elif region:
                query_echo = {"region": region, "sv_dataset": sv_dataset}
            shaped["query"] = query_echo
            # Cross-link each returned opaque id to the single-SV detail tool.
            existing_meta: dict[str, Any] = shaped.get("_meta") or {}
            existing_next: list[Any] = existing_meta.get("next_commands", [])
            next_commands = [
                {
                    "tool": "get_structural_variant",
                    "arguments": {"variant_id": row["variant_id"], "dataset": sv_dataset},
                }
                for row in shaped["structural_variants"][:_NEXT_COMMAND_CAP]
                if row.get("variant_id")
            ]
            shaped["_meta"] = {
                **existing_meta,
                "next_commands": [*existing_next, *next_commands],
            }
            return shaped

        return await run_mcp_tool(
            "search_structural_variants",
            call,
            context=McpErrorContext(
                tool_name="search_structural_variants",
                gene_id=gene_id,
                gene_symbol=gene_symbol,
                region=region,
                dataset=sv_dataset,
            ),
        )
