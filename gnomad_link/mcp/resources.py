"""Capabilities and usage payloads for the gnomAD Link MCP server."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

RESEARCH_USE_NOTICE = "Research use only; not for clinical decision support."

MCP_PROTOCOL_VERSION = "2025-06-18"


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
            "get_gene_details",
            "get_gene_variants",
            "get_clinvar_variant_details",
            "get_clinvar_meta",
            "liftover_variant",
            "get_structural_variant",
            "get_mitochondrial_variant",
            "get_region",
            "get_transcript_details",
            "search_genes",
            "resolve_variant_id",
            "search_variants",
        ],
        "deprecated_tools": {
            "search_variants": "Use resolve_variant_id; this alias is retained for one release.",
        },
        "limitations": [
            "Default local CI avoids live gnomAD calls.",
            "get_region capped at 100kb span; get_gene_variants capped at 500 rows.",
            "Population truncation: subcohort and sex-split rows are omitted by default.",
            RESEARCH_USE_NOTICE,
        ],
    }


def get_usage_resource() -> str:
    return (
        "# gnomAD Link MCP Usage\n\n"
        "Use CHROM-POS-REF-ALT variant IDs (GRCh38 by default) for SNV/indel frequencies. "
        "Use M-POS-REF-ALT for mitochondrial variants. Compact responses are the default; "
        "request `response_mode=\"full\"` for debugging and `include_subcohorts=True` to "
        "expand population subgroup rows.\n\n"
        f"{RESEARCH_USE_NOTICE}"
    )
