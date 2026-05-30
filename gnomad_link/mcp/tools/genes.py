"""Gene tools: get_gene_details, get_gene_variants."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool
from gnomad_link.mcp.schema_relax import relax_output_schema
from gnomad_link.mcp.shaping import shape_gene_details_compact, shape_gene_variants
from gnomad_link.models import Gene
from gnomad_link.services import FrequencyService


def register_gene_tools(mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]) -> None:
    @mcp.tool(
        name="get_gene_details",
        title="Get Gene Details",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=relax_output_schema(Gene.model_json_schema()),
        tags={"gene"},
    )
    async def get_gene_details(
        gene_id: Annotated[
            str | None,
            Field(
                description="Ensembl gene ID (preferred over symbol).",
                examples=["ENSG00000169174"],
            ),
        ] = None,
        gene_symbol: Annotated[
            str | None,
            Field(
                description="HGNC gene symbol, used if gene_id is absent.",
                examples=["PCSK9"],
            ),
        ] = None,
        reference_genome: Annotated[Literal["GRCh37", "GRCh38"], Field()] = "GRCh38",
        response_mode: Annotated[
            Literal["compact", "full"],
            Field(
                description=(
                    "compact drops heavy arrays (transcripts, exons, alt_transcripts) and "
                    "emits a truncated block; full passes through everything."
                )
            ),
        ] = "compact",
    ) -> dict[str, Any]:
        """Use this when a caller has a gene id or symbol and needs constraint scores (pLI/oe_lof), canonical transcript, and basic coordinates. Follow with get_gene_variants if they then need per-variant rows. Returns compact ~2kB, full up to ~30kB."""

        async def call() -> dict[str, Any]:
            if not gene_id and not gene_symbol:
                raise ValueError("Provide gene_id or gene_symbol.")
            service = service_factory()
            gene_obj = await service.get_gene(
                gene_id=gene_id,
                gene_symbol=gene_symbol,
                reference_genome=reference_genome,
            )
            result: dict[str, Any] = (
                gene_obj.model_dump() if hasattr(gene_obj, "model_dump") else dict(gene_obj)
            )
            if response_mode == "compact":
                result = shape_gene_details_compact(result)
            # Suggest the natural follow-up call using the resolved gene_id.
            resolved_id = result.get("gene_id") or gene_id
            if resolved_id:
                existing_meta: dict[str, Any] = result.get("_meta") or {}
                existing_next: list[Any] = existing_meta.get("next_commands", [])
                variants_cmd: dict[str, Any] = {
                    "tool": "get_gene_variants",
                    "arguments": {"gene_id": resolved_id},
                }
                result["_meta"] = {
                    **existing_meta,
                    "next_commands": [*existing_next, variants_cmd],
                }
            return result

        return await run_mcp_tool(
            "get_gene_details",
            call,
            context=McpErrorContext(
                tool_name="get_gene_details",
                gene_id=gene_id,
                gene_symbol=gene_symbol,
            ),
        )

    @mcp.tool(
        name="get_gene_variants",
        title="Get Gene Variants",
        annotations=READ_ONLY_OPEN_WORLD,
        tags={"gene"},
        output_schema=relax_output_schema(
            {
                "type": "object",
                "properties": {
                    "variants": {"type": "array", "items": {"type": "object"}},
                    "returned": {"type": "integer"},
                    "total_seen": {"type": "integer"},
                    "truncated": {"type": ["object", "null"]},
                },
                "required": ["variants", "returned", "total_seen"],
                "additionalProperties": True,
            }
        ),
    )
    async def get_gene_variants(
        gene_id: Annotated[
            str,
            Field(description="Ensembl gene ID.", examples=["ENSG00000169174"]),
        ],
        dataset: Annotated[
            Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"],
            Field(
                description="gnomad_r4 (GRCh38, default, largest cohort), gnomad_r3 (GRCh38, whole-genome), gnomad_r2_1 (GRCh37 legacy)",
                examples=["gnomad_r4"],
            ),
        ] = "gnomad_r4",
        limit: Annotated[
            int, Field(ge=1, le=500, description="Max variants returned (hard cap 500).")
        ] = 100,
        consequence: Annotated[
            str | None,
            Field(description="VEP major_consequence to keep (e.g. 'missense_variant')."),
        ] = None,
        max_af: Annotated[
            float | None,
            Field(ge=0.0, le=1.0, description="Drop variants whose AF exceeds this threshold."),
        ] = None,
        min_ac: Annotated[
            int | None, Field(ge=0, description="Drop variants whose AC is below this threshold.")
        ] = None,
        include_populations: Annotated[
            bool,
            Field(
                description=(
                    "Keep each variant's per-population breakdown (trimmed). Set False to "
                    "drop the population arrays entirely (keeps ac/an/af) for a lean list scan "
                    "— the biggest token saving."
                )
            ),
        ] = True,
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
            Field(description="Drop populations with allele_count == 0 from each variant."),
        ] = True,
    ) -> dict[str, Any]:
        """Use this when a caller wants per-variant rows inside a gene. Large genes (e.g. TTN) return tens of thousands of variants upstream; this tool caps at 500 and exposes consequence/AF/AC filters. Each variant's population breakdown is trimmed (drops subcohort, sex-split, and zero-AC rows; set include_populations=False to drop the arrays entirely for a ~30% leaner scan); the projection is described once in `population_projection`. Returns a `truncated` block whenever the cap fires. Returns ~5-45kB at the default limit=100 (lower the limit or set include_populations=False to shrink)."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            raw = await service.get_gene_variants(gene_id, dataset)
            return shape_gene_variants(
                raw,
                limit=limit,
                consequence=consequence,
                max_af=max_af,
                min_ac=min_ac,
                include_populations=include_populations,
                include_subcohorts=include_subcohorts,
                include_sex_split=include_sex_split,
                exclude_zero_populations=exclude_zero_populations,
            )

        return await run_mcp_tool(
            "get_gene_variants",
            call,
            context=McpErrorContext(
                tool_name="get_gene_variants",
                gene_id=gene_id,
                dataset=dataset,
            ),
        )
