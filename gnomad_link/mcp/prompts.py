"""Canonical workflow prompts for gnomAD Link MCP."""

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.patterns import GENE_SYMBOL_PATTERN
from gnomad_link.mcp.tools.clinvar import _CLINVAR_VARIANT_ID_PATTERN
from gnomad_link.mcp.tools.coordinates import _REGION_PATTERN
from gnomad_link.mcp.tools.variants import _AUTOSOMAL_VARIANT_ID_PATTERN


def register_workflow_prompts(mcp: FastMCP) -> None:
    """Register canonical workflow prompts that guide LLM callers through tool chains."""

    @mcp.prompt(name="variant_frequency_workflow")
    def variant_frequency_workflow(
        variant_id: Annotated[
            str,
            Field(
                pattern=_AUTOSOMAL_VARIANT_ID_PATTERN,
                description=(
                    "Autosomal CHROM-POS-REF-ALT variant id matching "
                    f"{_AUTOSOMAL_VARIANT_ID_PATTERN}."
                ),
            ),
        ],
    ) -> str:
        """Guide for looking up allele frequencies and optional ClinVar annotation."""
        return (
            f"Variant frequency workflow for {variant_id}:\n"
            "1. Call get_variant_frequencies(variant_id='{variant_id}', dataset='gnomad_r4') "
            "to get per-population allele counts and the summary block.\n"
            "2. Inspect summary.top_enriched_population and summary.overall_af for quick context.\n"
            "3. Optionally call get_clinvar_variant_details(variant_id='{variant_id}') "
            "to add clinical significance, review status, and gold stars.\n"
            "4. If the variant is not found, call resolve_variant_id(query='{variant_id}') "
            "to check for alternate IDs, then retry.\n"
            "Research use only; not for clinical decision support."
        ).replace("{variant_id}", variant_id)

    @mcp.prompt(name="gene_constraint_workflow")
    def gene_constraint_workflow(
        gene_symbol: Annotated[
            str,
            Field(
                pattern=GENE_SYMBOL_PATTERN,
                description=f"HGNC gene symbol matching {GENE_SYMBOL_PATTERN}.",
            ),
        ],
    ) -> str:
        """Guide for reviewing gene constraint metrics and variant inventory."""
        return (
            f"Gene constraint workflow for {gene_symbol}:\n"
            "1. Call search_genes(query='{gene_symbol}') to resolve to an Ensembl gene_id.\n"
            "2. Call get_gene_details(gene_id='<resolved_id>') for pLI/oe_lof scores, "
            "canonical transcript, and coordinates.\n"
            "3. Call get_gene_variants(gene_id='<resolved_id>', consequence='frameshift_variant') "
            "to review loss-of-function variants. Raise limit or relax filters as needed.\n"
            "4. The summary.max_pop_af field in frequencies shows population enrichment.\n"
            "Research use only; not for clinical decision support."
        ).replace("{gene_symbol}", gene_symbol)

    @mcp.prompt(name="clinical_variant_workflow")
    def clinical_variant_workflow(
        variant_id: Annotated[
            str,
            Field(
                pattern=_CLINVAR_VARIANT_ID_PATTERN,
                description=(
                    f"ClinVar CHROM-POS-REF-ALT variant id matching {_CLINVAR_VARIANT_ID_PATTERN}."
                ),
            ),
        ],
    ) -> str:
        """Guide for a clinically oriented variant review combining ClinVar and gnomAD."""
        return (
            f"Clinical variant workflow for {variant_id}:\n"
            "1. Call get_clinvar_variant_details(variant_id='{variant_id}') for "
            "clinical significance, gold-star review status, and submitter list.\n"
            "2. Call get_variant_frequencies(variant_id='{variant_id}') to cross-check "
            "population frequency against the ClinVar assertion.\n"
            "3. Check summary.top_enriched_population and summary.overall_af from "
            "get_variant_frequencies.\n"
            "IMPORTANT: ClinVar entries reflect submitter assertions and are not a clinical "
            "diagnosis. Not for clinical decision support."
        ).replace("{variant_id}", variant_id)

    @mcp.prompt(name="region_scan_workflow")
    def region_scan_workflow(
        region: Annotated[
            str,
            Field(
                pattern=_REGION_PATTERN,
                description=f"Region in CHROM-START-STOP form matching {_REGION_PATTERN}.",
            ),
        ],
    ) -> str:
        """Guide for scanning a genomic region for variants and overlapping genes."""
        return (
            f"Region scan workflow for {region}:\n"
            "1. Call get_region(region='{region}', include_clinvar=True, include_genes=True). "
            "Maximum span is 100kb; larger windows are clamped automatically.\n"
            "2. If a truncated block appears, reduce the window or call get_region "
            "in consecutive tiles.\n"
            "3. For per-variant frequency data on a gene in the region, follow with "
            "get_gene_variants(gene_id='<gene_id from region response>').\n"
            "Research use only; not for clinical decision support."
        ).replace("{region}", region)
