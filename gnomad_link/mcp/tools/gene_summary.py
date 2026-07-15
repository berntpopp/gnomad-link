"""Gene summary tool: get_gene_summary (one-shot gene dossier)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool
from gnomad_link.mcp.gene_summary_shaping import rank_pathogenic_clinvar
from gnomad_link.mcp.headline import gene_summary_headline
from gnomad_link.mcp.minimal_shaping import project_gene_summary_minimal
from gnomad_link.mcp.patterns import split_gene
from gnomad_link.services import FrequencyService


def register_gene_summary_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="get_gene_summary",
        title="Get Gene Summary",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=None,
        tags={"gene"},
    )
    async def get_gene_summary(
        gene: Annotated[
            str,
            Field(
                description="Gene symbol (e.g. PCSK9) or Ensembl gene ID (ENSG...).",
                examples=["PCSK9"],
            ),
        ],
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
            Literal["compact", "full", "minimal"],
            Field(
                description=(
                    "compact ranks pathogenic ClinVar into clinvar_summary; full returns the raw "
                    "clinvar_variants list; minimal returns the headline + top-line constraint + "
                    "ClinVar pathogenic COUNT + _meta only. All honor "
                    "include_clinvar/include_constraint."
                )
            ),
        ] = "compact",
    ) -> dict[str, Any]:
        """Use this when a caller wants a one-shot gene dossier: constraint (pLI/oe_lof), canonical and MANE-Select transcripts, top pathogenic ClinVar variants, and expression (mean pext + top GTEx tissues). Pass a gene symbol (e.g. PCSK9) or Ensembl gene ID (ENSG...). Use include_clinvar / include_constraint / include_expression to fetch only the sections you need (e.g. include_clinvar=false + include_constraint=false for expression-only). Follow with get_gene_variants for per-variant rows. Returns compact ~3-8kB (ClinVar-dependent); include_clinvar=false trims it most."""

        gene_id, gene_symbol = split_gene(gene)

        async def call() -> dict[str, Any]:
            service = service_factory()
            summary = await service.get_gene_summary(
                gene_id=gene_id,
                gene_symbol=gene_symbol,
                dataset=dataset,
                include_expression=include_expression,
            )

            result: dict[str, Any] = dict(summary)
            # The raw `pext` block is a {"regions":[...]} dict-of-lists redundant with
            # the `expression.mean_pext` summary; drop it outside full mode. Keeping it
            # also made this single-gene RECORD read as a multi-row collection.
            if response_mode != "full":
                result.pop("pext", None)
            if not include_expression:
                result.pop("expression", None)
            if not include_constraint:
                result.pop("constraint", None)
            if include_clinvar:
                if response_mode in ("compact", "minimal"):
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
            ]
            # Defect #45-5: a get_clinvar_variant_details command MUST carry a real
            # variant_id (its required parameter) — a ready-to-call command must be
            # callable. Interpolate the top pathogenic variant; OMIT the entry when
            # none is available rather than emit an uncallable command.
            top_pathogenic = (result.get("clinvar_summary") or {}).get("top_pathogenic") or []
            top_variant_id = top_pathogenic[0].get("variant_id") if top_pathogenic else None
            if top_variant_id:
                next_commands.append(
                    {
                        "tool": "get_clinvar_variant_details",
                        "arguments": {
                            "variant_id": top_variant_id,
                            "reference_genome": (
                                "GRCh37" if dataset == "gnomad_r2_1" else "GRCh38"
                            ),
                        },
                    }
                )
            next_commands.append(
                {"tool": "get_coverage", "arguments": {"target": resolved_id}},
            )
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
            shaped = {"headline": gene_summary_headline(result, dataset=dataset), **result}
            if response_mode == "minimal":
                return project_gene_summary_minimal(shaped)
            return shaped

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
