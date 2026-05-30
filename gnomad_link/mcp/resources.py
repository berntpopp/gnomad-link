"""Capabilities and usage payloads for the gnomAD Link MCP server."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

RESEARCH_USE_NOTICE = "Research use only; not for clinical decision support."

MCP_PROTOCOL_VERSION = "2025-06-18"

# Current gnomAD upstream release. Surfaced in every MCP response's `_meta`
# so LLM callers can cite the precise data version. v4.1.0 was released
# 2024-11; bump this constant when upstream revs.
GNOMAD_DATA_RELEASE = "4.1.0"


def _server_version() -> str:
    try:
        return version("gnomad-link")
    except PackageNotFoundError:
        return "unknown"


def get_capabilities_resource() -> dict[str, Any]:
    return {
        "server": "gnomad-link",
        "server_version": _server_version(),
        "mcp_protocol_version": MCP_PROTOCOL_VERSION,
        "gnomad_release": GNOMAD_DATA_RELEASE,
        # Populated by a startup probe in a future task; remains None when the
        # probe is unavailable so callers can still discover the field shape.
        "clinvar_release_date": None,
        "research_use_only": True,
        "datasets": {
            "gnomad_r2_1": {"reference_genome": "GRCh37"},
            "gnomad_r3": {"reference_genome": "GRCh38"},
            "gnomad_r4": {"reference_genome": "GRCh38", "default": True},
        },
        "sv_datasets": ["gnomad_sv_r2_1", "gnomad_sv_r4"],
        "population_codes": [
            "afr",
            "amr",
            "asj",
            "eas",
            "fin",
            "nfe",
            "sas",
            "mid",
            "ami",
            "remaining",
        ],
        "population_suffixes": {
            "_XX": "sex-split XX population row when present",
            "_XY": "sex-split XY population row when present",
        },
        "recommended_workflows": [
            "variant_id -> get_variant_frequencies",
            "rsID or loose text -> resolve_variant_id -> get_variant_frequencies",
            "gene symbol -> search_genes -> get_gene_details",
            "clinical annotation -> get_clinvar_variant_details + get_variant_frequencies",
            "build conversion -> liftover_variant",
            "region scan -> get_region (cap span at 100kb; use include_clinvar/include_genes)",
        ],
        "tools": [
            "get_server_capabilities",
            "get_variant_frequencies",
            "get_variant_details",
            "compare_variant_across_datasets",
            "get_gene_details",
            "get_gene_variants",
            "get_gene_summary",
            "get_clinvar_variant_details",
            "get_clinvar_meta",
            "liftover_variant",
            "get_structural_variant",
            "search_structural_variants",
            "get_mitochondrial_variant",
            "get_region",
            "get_coverage",
            "get_transcript_details",
            "search_genes",
            "resolve_variant_id",
            "search_variants",
            "compute_carrier_frequency",
            "compute_gene_carrier_frequency",
            "get_gnomad_diagnostics",
        ],
        "deprecated_tools": {
            "search_variants": "Use resolve_variant_id; this alias is retained for one release.",
            "get_clinvar_meta": "Use get_server_capabilities; this tool will be removed in a future release.",
        },
        "token_cost_hints": {
            "get_server_capabilities": "<2kB",
            "get_variant_frequencies": "~2-4kB",
            "get_variant_details": "compact ~3kB, full up to ~50kB",
            "compare_variant_across_datasets": "~3-8kB (dataset/liftover dependent)",
            "get_gene_details": "compact ~2kB, full up to ~30kB",
            "get_gene_variants": "~5-50kB (limit-dependent)",
            "get_gene_summary": "compact ~3-8kB, full up to ~40kB",
            "get_clinvar_variant_details": "~3-15kB (submissions_limit dependent)",
            "get_clinvar_meta": "<1kB",
            "liftover_variant": "<1kB",
            "get_structural_variant": "~1-3kB",
            "search_structural_variants": "~3-30kB (limit-dependent)",
            "get_mitochondrial_variant": "~2-4kB",
            "get_region": "~5-50kB",
            "get_coverage": "compact ~3-40kB (bin-count dependent), full larger",
            "get_transcript_details": "~5-15kB",
            "search_genes": "~1-3kB",
            "resolve_variant_id": "~1-5kB (enrichment dependent)",
            "search_variants": "~1-5kB (deprecated alias)",
            "compute_carrier_frequency": "~2-4kB (per-population dependent)",
            "compute_gene_carrier_frequency": "~4-30kB (gene/limit dependent)",
            "get_gnomad_diagnostics": "<1kB",
        },
        "limitations": [
            "Default local CI avoids live gnomAD calls.",
            "get_region capped at 100kb span; get_gene_variants capped at 500 rows.",
            "Population truncation: subcohort and sex-split rows are omitted by default.",
            RESEARCH_USE_NOTICE,
        ],
        "llm_driver_contract": {
            "recommended_entrypoint": "get_server_capabilities",
            "core_workflow_tools": [
                "resolve_variant_id",
                "get_variant_frequencies",
                "search_genes",
                "get_gene_details",
                "get_clinvar_variant_details",
                "liftover_variant",
            ],
        },
        "output_cheatsheet": {
            "variant_id_field": "variant_id",
            "exome_populations": "exome.populations[]",
            "genome_populations": "genome.populations[]",
            "summary_block": "summary",
            "truncation_block": "exome.truncated",
        },
        "tool_categories": {
            "variant": [
                "get_variant_frequencies",
                "get_variant_details",
                "compare_variant_across_datasets",
                "get_mitochondrial_variant",
                "get_structural_variant",
                "search_structural_variants",
                "compute_carrier_frequency",
            ],
            "gene": [
                "get_gene_details",
                "get_gene_variants",
                "get_gene_summary",
                "compute_gene_carrier_frequency",
                "search_genes",
            ],
            "clinical": ["get_clinvar_variant_details", "get_clinvar_meta"],
            "coordinates": [
                "liftover_variant",
                "get_region",
                "get_transcript_details",
                "get_coverage",
            ],
            "search": [
                "search_genes",
                "resolve_variant_id",
                "search_variants",
                "search_structural_variants",
            ],
            "metadata": ["get_server_capabilities", "get_gnomad_diagnostics"],
        },
    }


def get_usage_resource() -> str:
    return (
        "# gnomAD Link MCP Usage\n\n"
        "Use CHROM-POS-REF-ALT variant IDs (GRCh38 by default) for SNV/indel frequencies. "
        "Use M-POS-REF-ALT for mitochondrial variants. Compact responses are the default; "
        'request `response_mode="full"` for debugging and `include_subcohorts=True` to '
        "expand population subgroup rows.\n\n"
        f"{RESEARCH_USE_NOTICE}"
    )
