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
from gnomad_link.mcp.schema_relax import relax_output_schema
from gnomad_link.services import FrequencyService
from gnomad_link.services.gene_carrier_filters import FilterConfig

_GENE_ID_PATTERN = r"^ENSG\d{11}$"
_GENE_SYMBOL_PATTERN = r"^[A-Za-z0-9._-]{1,32}$"

_GENE_CARRIER_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "gene": {"type": ["object", "null"]},
        "dataset": {"type": "string"},
        "global": {"type": ["object", "null"]},
        "populations": {"type": "array"},
        "contributing_variants": {"type": ["object", "null"]},
    },
    "required": ["dataset"],
    "additionalProperties": True,
}


def register_gene_carrier_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="compute_gene_carrier_frequency",
        title="Compute Gene Carrier Frequency",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=relax_output_schema(_GENE_CARRIER_OUTPUT_SCHEMA),
        tags={"gene"},
    )
    async def compute_gene_carrier_frequency(
        gene_symbol: Annotated[
            str | None,
            Field(
                default=None,
                description="HGNC gene symbol (e.g. CFTR). Provide exactly one of gene_symbol/gene_id.",
                pattern=_GENE_SYMBOL_PATTERN,
                examples=["CFTR"],
            ),
        ] = None,
        gene_id: Annotated[
            str | None,
            Field(
                default=None,
                description="Ensembl gene ID (ENSG...). Provide exactly one of gene_symbol/gene_id.",
                pattern=_GENE_ID_PATTERN,
                examples=["ENSG00000001626"],
            ),
        ] = None,
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
            Field(description="Include conflicting ClinVar variants resolved by submission share."),
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
            Literal["compact", "full"],
            Field(description="compact caps the contributing-variant list; full returns all."),
        ] = "compact",
        top_variants_limit: Annotated[
            int, Field(ge=1, le=200, description="Cap on contributing variants in compact mode.")
        ] = 25,
    ) -> dict[str, Any]:
        """Use this when a caller needs the GENE-level autosomal-recessive carrier frequency (all qualifying pathogenic variants summed), not a single variant. Provide exactly one of gene_symbol or gene_id. Mirrors the gnomad-carrier-frequency calculator: LoF-HC + missense/other with ClinVar P/LP (>= star threshold), per-population + global carrier frequency via GCR (homozygote exclusion) by default, with genetic and Bayesian prevalence. Toggle filters, method, penetrance, and quality exclusions. Research use only; not clinical decision support. Returns ~4-30kB (gene/limit dependent)."""

        provided = [("gene_symbol", gene_symbol), ("gene_id", gene_id)]
        set_args = [name for name, value in provided if value]

        async def call() -> dict[str, Any]:
            if len(set_args) != 1:
                raise ValueError(
                    f"Provide exactly one of gene_symbol or gene_id (got {len(set_args)}: {set_args})."
                )
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
            return result

        return await run_mcp_tool(
            "compute_gene_carrier_frequency",
            call,
            context=McpErrorContext(
                tool_name="compute_gene_carrier_frequency",
                dataset=dataset,
            ),
        )
