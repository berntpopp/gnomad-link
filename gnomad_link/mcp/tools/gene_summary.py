"""Gene summary tool: get_gene_summary (one-shot gene dossier)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool
from gnomad_link.mcp.gene_summary_shaping import rank_pathogenic_clinvar
from gnomad_link.mcp.schema_relax import relax_output_schema
from gnomad_link.services import FrequencyService

_GENE_SUMMARY_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "gene_id": {"type": ["string", "null"]},
        "symbol": {"type": ["string", "null"]},
        "name": {"type": ["string", "null"]},
        "coords": {"type": ["object", "null"]},
        "dataset": {"type": "string"},
        "constraint": {"type": ["object", "null"]},
        "canonical_transcript_id": {"type": ["string", "null"]},
        "mane_select_transcript": {"type": ["object", "null"]},
        "clinvar_summary": {"type": ["object", "null"]},
        "clinvar_variants": {"type": ["array", "null"], "items": {"type": "object"}},
        "expression": {"type": ["object", "null"]},
        "partial": {"type": "boolean"},
    },
    "required": ["dataset"],
    "additionalProperties": True,
}


def register_gene_summary_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="get_gene_summary",
        title="Get Gene Summary",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=relax_output_schema(_GENE_SUMMARY_OUTPUT_SCHEMA),
        tags={"gene"},
    )
    async def get_gene_summary(
        gene_symbol: Annotated[
            str | None,
            Field(description="HGNC gene symbol; provide this OR gene_id.", examples=["PCSK9"]),
        ] = None,
        gene_id: Annotated[
            str | None,
            Field(
                description="Ensembl gene ID; provide this OR gene_symbol.",
                examples=["ENSG00000169174"],
            ),
        ] = None,
        dataset: Annotated[
            Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"],
            Field(
                description="gnomad_r4 (GRCh38, default), gnomad_r3 (GRCh38), gnomad_r2_1 (GRCh37 legacy)",
                examples=["gnomad_r4"],
            ),
        ] = "gnomad_r4",
        clinvar_limit: Annotated[
            int,
            Field(ge=1, le=50, description="Cap on top_pathogenic ClinVar rows in compact mode."),
        ] = 10,
        include_expression: Annotated[
            bool,
            Field(description="Include the best-effort GRCh37 expression block (pext + GTEx)."),
        ] = True,
        response_mode: Annotated[
            Literal["compact", "full"],
            Field(
                description=(
                    "compact ranks pathogenic ClinVar into clinvar_summary and trims expression; "
                    "full returns the raw clinvar_variants list and untrimmed expression."
                )
            ),
        ] = "compact",
    ) -> dict[str, Any]:
        """Use this when a caller wants a one-shot gene dossier: constraint (pLI/oe_lof), canonical and MANE-Select transcripts, top pathogenic ClinVar variants, and expression (pext + GTEx). Provide exactly one of gene_symbol/gene_id. Follow with get_gene_variants for per-variant rows. Returns compact ~3-8kB."""

        async def call() -> dict[str, Any]:
            if bool(gene_symbol) == bool(gene_id):
                raise ValueError("Provide exactly one of gene_symbol or gene_id.")
            service = service_factory()
            summary = await service.get_gene_summary(
                gene_id=gene_id,
                gene_symbol=gene_symbol,
                dataset=dataset,
            )

            result: dict[str, Any] = dict(summary)
            if not include_expression:
                result.pop("expression", None)
            if response_mode == "compact":
                raw_clinvar = result.pop("clinvar_variants", None) or []
                result["clinvar_summary"] = rank_pathogenic_clinvar(
                    raw_clinvar, clinvar_limit=clinvar_limit
                )

            resolved_id = result.get("gene_id") or gene_id
            existing_meta: dict[str, Any] = result.get("_meta") or {}
            existing_next: list[Any] = existing_meta.get("next_commands", [])
            next_commands: list[dict[str, Any]] = [
                {"tool": "get_gene_variants", "arguments": {"gene_id": resolved_id}},
                {
                    "tool": "get_clinvar_variant_details",
                    "arguments": {
                        "reference_genome": "GRCh37" if dataset == "gnomad_r2_1" else "GRCh38"
                    },
                },
                {"tool": "get_coverage", "arguments": {"gene_id": resolved_id}},
            ]
            result["_meta"] = {
                **existing_meta,
                "next_commands": [*existing_next, *next_commands][:3],
            }
            return result

        return await run_mcp_tool(
            "get_gene_summary",
            call,
            context=McpErrorContext(
                tool_name="get_gene_summary",
                gene_id=gene_id,
                gene_symbol=gene_symbol,
                dataset=dataset,
            ),
        )
