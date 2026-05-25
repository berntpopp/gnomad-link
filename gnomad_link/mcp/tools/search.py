"""Search and identifier-resolution tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool
from gnomad_link.models import GeneSearchResult, VariantSearchResult
from gnomad_link.services import FrequencyService


def register_search_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="search_genes",
        title="Search Genes",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema={
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": GeneSearchResult.model_json_schema(),
                },
                "returned": {"type": "integer"},
                "truncated": {"type": ["object", "null"]},
            },
            "required": ["results", "returned"],
        },
    )
    async def search_genes(
        query: Annotated[
            str,
            Field(
                min_length=2,
                max_length=100,
                description="Gene symbol, name fragment, or Ensembl ID.",
            ),
        ],
        reference_genome: Annotated[
            Literal["GRCh37", "GRCh38"], Field()
        ] = "GRCh38",
        limit: Annotated[
            int,
            Field(ge=1, le=50, description="Max matches returned."),
        ] = 25,
    ) -> dict[str, Any]:
        """Use this when a caller has a fuzzy gene query (symbol, alias, partial name). Follow with get_gene_details for full constraint metrics."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            raw = await service.search_genes(query, reference_genome)
            total = len(raw)
            items = raw[:limit]
            results = [
                r.model_dump() if isinstance(r, GeneSearchResult) else r
                for r in items
            ]
            payload: dict[str, Any] = {"results": results, "returned": len(results)}
            if total > len(results):
                payload["truncated"] = {
                    "kind": "search_results",
                    "total_seen": total,
                    "to_disable": "raise limit (max 50) or refine the query",
                }
            return payload

        return await run_mcp_tool(
            "search_genes",
            call,
            context=McpErrorContext(tool_name="search_genes"),
        )

    @mcp.tool(
        name="resolve_variant_id",
        title="Resolve Variant Identifier",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema={
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": VariantSearchResult.model_json_schema(),
                },
                "returned": {"type": "integer"},
                "next_steps": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["results", "returned", "next_steps"],
        },
    )
    async def resolve_variant_id(
        query: Annotated[
            str,
            Field(
                min_length=3,
                max_length=100,
                description="rsID, CHROM-POS-REF-ALT, or 'CHROM:POS'.",
            ),
        ],
        dataset: Annotated[
            Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"], Field()
        ] = "gnomad_r4",
        limit: Annotated[int, Field(ge=1, le=25)] = 10,
    ) -> dict[str, Any]:
        """Use this when the caller only has an rsID, partial coordinates, or text fragment and needs to obtain a canonical gnomAD variant id. Returns IDs only -- call get_variant_frequencies or get_variant_details next."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            # search_variants returns list[str] (variant IDs); wrap as VariantSearchResult dicts
            raw = await service.search_variants(query, dataset)
            results = [{"variant_id": vid} for vid in raw[:limit]]
            return {
                "results": results,
                "returned": len(results),
                "next_steps": [
                    "Pick one variant_id and call get_variant_frequencies(variant_id, dataset).",
                    "Or call get_variant_details(variant_id, dataset) for annotations.",
                ],
            }

        return await run_mcp_tool(
            "resolve_variant_id",
            call,
            context=McpErrorContext(tool_name="resolve_variant_id"),
        )

    @mcp.tool(
        name="search_variants",
        title="Search Variants (deprecated alias)",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema={
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": VariantSearchResult.model_json_schema(),
                },
                "returned": {"type": "integer"},
                "next_steps": {"type": "array", "items": {"type": "string"}},
                "_meta": {"type": "object"},
            },
            "required": ["results", "returned", "next_steps"],
        },
    )
    async def search_variants(
        query: Annotated[str, Field(min_length=3, max_length=100)],
        dataset: Annotated[
            Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"], Field()
        ] = "gnomad_r4",
        limit: Annotated[int, Field(ge=1, le=25)] = 10,
    ) -> dict[str, Any]:
        """Use this when a caller uses the legacy tool name -- deprecated alias for resolve_variant_id. Same behaviour; will be removed in the next release."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            # search_variants returns list[str] (variant IDs); wrap as VariantSearchResult dicts
            raw = await service.search_variants(query, dataset)
            results = [{"variant_id": vid} for vid in raw[:limit]]
            return {
                "results": results,
                "returned": len(results),
                "next_steps": [
                    "Pick one variant_id and call get_variant_frequencies(variant_id, dataset).",
                ],
                "_meta": {"deprecated": True, "use_instead": "resolve_variant_id"},
            }

        return await run_mcp_tool(
            "search_variants",
            call,
            context=McpErrorContext(tool_name="search_variants"),
        )
