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
            Field(
                description="Include the best-effort expression block (mean pext + top GTEx "
                "tissues). False skips the extra GTEx upstream call."
            ),
        ] = True,
        include_clinvar: Annotated[
            bool,
            Field(
                description="Include the ClinVar block. False drops it entirely (~10kB saved on "
                "ClinVar-dense genes) — combine with include_constraint=False for expression-only.",
            ),
        ] = True,
        include_constraint: Annotated[
            bool,
            Field(description="Include the gnomAD constraint block (pLI/oe_lof)."),
        ] = True,
        response_mode: Annotated[
            Literal["compact", "full"],
            Field(
                description=(
                    "compact ranks pathogenic ClinVar into clinvar_summary; full returns the raw "
                    "clinvar_variants list. Both honor include_clinvar/include_constraint."
                )
            ),
        ] = "compact",
    ) -> dict[str, Any]:
        """Use this when a caller wants a one-shot gene dossier: constraint (pLI/oe_lof), canonical and MANE-Select transcripts, top pathogenic ClinVar variants, and expression (mean pext + top GTEx tissues). Provide exactly one of gene_symbol/gene_id. Use include_clinvar / include_constraint / include_expression to fetch only the sections you need (e.g. include_clinvar=false + include_constraint=false for expression-only). Follow with get_gene_variants for per-variant rows. Returns compact ~3-8kB (ClinVar-dependent); include_clinvar=false trims it most."""

        async def call() -> dict[str, Any]:
            if bool(gene_symbol) == bool(gene_id):
                raise ValueError("Provide exactly one of gene_symbol or gene_id.")
            service = service_factory()
            summary = await service.get_gene_summary(
                gene_id=gene_id,
                gene_symbol=gene_symbol,
                dataset=dataset,
                include_expression=include_expression,
            )

            result: dict[str, Any] = dict(summary)
            if not include_expression:
                result.pop("expression", None)
            if not include_constraint:
                result.pop("constraint", None)
            if include_clinvar:
                if response_mode == "compact":
                    raw_clinvar = result.pop("clinvar_variants", None) or []
                    result["clinvar_summary"] = rank_pathogenic_clinvar(
                        raw_clinvar, clinvar_limit=clinvar_limit
                    )
                # full mode keeps the raw clinvar_variants list as-is.
            else:
                result.pop("clinvar_variants", None)
                result.pop("clinvar_summary", None)

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
            # Dedupe by tool name so a repeated command never fills a slot twice.
            deduped: list[dict[str, Any]] = []
            seen: set[str] = set()
            for cmd in [*existing_next, *next_commands]:
                tool_name = cmd.get("tool")
                if tool_name in seen:
                    continue
                seen.add(tool_name)
                deduped.append(cmd)
            result["_meta"] = {**existing_meta, "next_commands": deduped[:3]}
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
