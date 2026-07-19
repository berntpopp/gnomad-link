"""Gene-level carrier-frequency tool: compute_gene_carrier_frequency.

Sums qualifying pathogenic variants across a gene per population (ports the
gnomad-carrier-frequency algorithm). Distinct from the single-variant
compute_carrier_frequency tool.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool
from gnomad_link.mcp.gene_carrier_shaping import shape_gene_carrier
from gnomad_link.mcp.minimal_shaping import project_gene_carrier_frequency_minimal
from gnomad_link.mcp.patterns import split_gene
from gnomad_link.services import FrequencyService
from gnomad_link.services.gene_carrier_filters import FilterConfig


def register_gene_carrier_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="compute_gene_carrier_frequency",
        title="Compute Gene Carrier Frequency",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=None,
        tags={"gene"},
    )
    async def compute_gene_carrier_frequency(
        gene: Annotated[
            str,
            Field(
                description="Gene symbol (e.g. CFTR) or Ensembl gene ID (ENSG...).",
                examples=["CFTR"],
            ),
        ],
        dataset: Annotated[
            Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"],
            Field(
                description="gnomad_r4 (GRCh38, default), gnomad_r3 (GRCh38), gnomad_r2_1 (GRCh37)."
            ),
        ] = "gnomad_r4",
        include_lof_hc: Annotated[
            bool, Field(description="Count LOFTEE high-confidence LoF on the canonical transcript.")
        ] = True,
        include_missense: Annotated[
            bool, Field(description="Count missense/inframe variants (requires ClinVar P/LP).")
        ] = True,
        include_clinvar: Annotated[
            bool, Field(description="Use ClinVar Pathogenic/Likely-pathogenic evidence.")
        ] = True,
        clinvar_star_threshold: Annotated[
            int, Field(ge=0, le=4, description="Minimum ClinVar gold stars for a P/LP match.")
        ] = 2,
        include_conflicting_clinvar: Annotated[
            bool,
            Field(
                description="Include conflicting ClinVar variants, resolved by P/LP "
                "submission share. Resolution is batched server-side (~1 extra request "
                "per 24 conflicting variants), so this stays fast.",
            ),
        ] = False,
        conflicting_threshold: Annotated[
            float,
            Field(
                ge=50,
                le=100,
                description="Min %% of P/LP submissions to accept a conflicting variant.",
            ),
        ] = 80.0,
        method: Annotated[
            Literal["hom_exclusion", "hwe", "simplified"],
            Field(
                description="hom_exclusion=GCR 1-prod(1-VCR) (default); hwe=2pq; simplified=2*sum(AF).",
            ),
        ] = "hom_exclusion",
        penetrance: Annotated[
            float,
            Field(ge=0, le=1, description="Penetrance for Bayesian prevalence (q^2 * penetrance)."),
        ] = 1.0,
        exclude_high_af: Annotated[
            bool, Field(description="Drop variants with AF >= 0.05 (ACMG BA1) instead of flagging.")
        ] = False,
        exclude_high_hom: Annotated[
            bool, Field(description="Drop variants with excess homozygotes instead of flagging.")
        ] = False,
        exclude_gnomad_filtered: Annotated[
            bool, Field(description="Drop variants that failed gnomAD QC filters.")
        ] = False,
        exclude_genomes_only: Annotated[
            bool, Field(description="Drop genome-only variants.")
        ] = False,
        response_mode: Annotated[
            Literal["compact", "full", "minimal"],
            Field(
                description="compact caps the contributing-variant list; full returns all; "
                "minimal returns the headline + global block + contributing-variant COUNT + _meta "
                "(drops per-population rows and the contributing-variant list)."
            ),
        ] = "compact",
        top_variants_limit: Annotated[
            int, Field(ge=1, le=200, description="Cap on contributing variants in compact mode.")
        ] = 25,
    ) -> dict[str, Any]:
        """Use this when a caller needs gene-level autosomal-recessive carrier frequency across qualifying pathogenic variants, not a single variant. Run this server-side computation once per gene; do not loop over variants. Returns global and per-population carrier frequency, genetic and Bayesian prevalence, a headline, provenance, and contributing variants. Research use only; not clinical decision support. Returns ~4-30kB (gene/limit dependent)."""

        gene_id, gene_symbol = split_gene(gene)

        async def call() -> dict[str, Any]:
            service = service_factory()
            raw = await service.get_gene_carrier_frequency(
                gene_id=gene_id,
                gene_symbol=gene_symbol,
                dataset=dataset,
                filter_config=FilterConfig(
                    lof_hc_enabled=include_lof_hc,
                    missense_enabled=include_missense,
                    clinvar_enabled=include_clinvar,
                    clinvar_star_threshold=clinvar_star_threshold,
                    include_conflicting=include_conflicting_clinvar,
                    conflicting_threshold=conflicting_threshold,
                ),
                method=method,
                penetrance=penetrance,
                exclude_high_af=exclude_high_af,
                exclude_high_hom=exclude_high_hom,
                exclude_gnomad_filtered=exclude_gnomad_filtered,
                exclude_genomes_only=exclude_genomes_only,
            )
            result = shape_gene_carrier(
                raw, response_mode=response_mode, top_variants_limit=top_variants_limit
            )
            result["_meta"] = {
                "next_commands": [
                    {
                        "tool": "get_gene_variants",
                        "arguments": {
                            "gene_id": raw.get("gene", {}).get("gene_id"),
                            "dataset": dataset,
                        },
                    },
                    {
                        "tool": "get_clinvar_variant_details",
                        "arguments": {"variant_id": "<contributing variant_id>"},
                    },
                ]
            }
            if response_mode == "minimal":
                return project_gene_carrier_frequency_minimal(result)
            return result

        return await run_mcp_tool(
            "compute_gene_carrier_frequency",
            call,
            context=McpErrorContext(
                tool_name="compute_gene_carrier_frequency",
                dataset=dataset,
            ),
        )
