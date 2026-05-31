"""Capabilities and usage payloads for the gnomAD Link MCP server."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

from mcp.types import LATEST_PROTOCOL_VERSION as MCP_PROTOCOL_VERSION

from gnomad_link.config import settings
from gnomad_link.mcp.clinvar_date_cache import get_cached_clinvar_release_date

RESEARCH_USE_NOTICE = "Research use only; not for clinical decision support."

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
        # Echoes the process-cached live ClinVar release date once the first
        # get_server_capabilities tool call has fetched it; None until then (the
        # sync resource handler never calls upstream itself).
        "clinvar_release_date": get_cached_clinvar_release_date(),
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
            "gene symbol -> compute_gene_carrier_frequency (gene-level recessive carrier rate)",
            "clinical annotation -> get_clinvar_variant_details + get_variant_frequencies",
            "build conversion -> liftover_variant",
            "region scan -> get_region (cap span at 100kb; use include_clinvar/include_genes)",
        ],
        "prompts": {
            "variant_frequency_workflow": ["variant_id"],
            "gene_constraint_workflow": ["gene_symbol"],
            "clinical_variant_workflow": ["variant_id"],
            "region_scan_workflow": ["region"],
        },
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
            "get_server_capabilities": "~7kB (discovery surface; detailed contracts in gnomad://reference)",
            "get_variant_frequencies": "~2-4kB",
            "get_variant_details": "compact ~3-6kB (population-trimmed), full up to ~50kB",
            "compare_variant_across_datasets": "~3-8kB (dataset/liftover dependent)",
            "get_gene_details": "compact ~2kB, full up to ~30kB",
            "get_gene_variants": "~5-45kB at limit=100 (include_populations=False ~30% leaner)",
            "get_gene_summary": "compact ~3-8kB (ClinVar-dependent), full up to ~40kB",
            "get_clinvar_variant_details": "~3-15kB (submissions_limit dependent)",
            "get_clinvar_meta": "<1kB",
            "liftover_variant": "<1kB",
            "get_structural_variant": "compact ~1-4kB (zero-AC/sex-split pops trimmed), full ~10-20kB",
            "search_structural_variants": "~3-30kB (limit-dependent)",
            "get_mitochondrial_variant": "compact ~1-3kB (zero/sex-split rows trimmed), full larger",
            "get_region": "~5-50kB",
            "get_coverage": "compact ~3-40kB (bin-count dependent), full larger",
            "get_transcript_details": "~3-8kB (include_expression dependent)",
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
            "Population truncation: subcohort, sex-split, and zero-AC rows are omitted by "
            "default across get_variant_frequencies, get_variant_details, and get_gene_variants.",
            "search_genes uses gnomAD's bounded autocomplete; a short gene-family prefix can "
            "omit exact members (e.g. 'GRIN' omits GRIN1/GRIN2B) -- query the full symbol.",
            RESEARCH_USE_NOTICE,
        ],
        "concurrency": {
            "max_concurrent_requests": settings.GNOMAD_MAX_CONCURRENCY,
            "queue_wait_seconds": settings.GNOMAD_QUEUE_WAIT_TIMEOUT,
            "guidance": (
                "The server caps in-flight upstream requests at this value. Fan out tool "
                "calls in batches no larger than this; excess concurrent calls wait up to "
                "queue_wait_seconds then receive a retryable rate_limited error (back off "
                "and retry), not a timeout."
            ),
            "internal_fanout": (
                "compute_gene_carrier_frequency batches ClinVar conflicting-resolution into "
                "ceil(N/24) concurrent upstream calls, so a single large-gene call can itself "
                "saturate the queue."
            ),
            "sequential_fanout": (
                "compare_variant_across_datasets issues ~4 sequential upstream calls per "
                "invocation (one variant query per dataset plus the gnomad_r2_1 liftover), so "
                "N concurrent compare calls hold N slots continuously for the duration."
            ),
        },
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
            "headline_field": "headline",
            "truncation_block": "exome.truncated",
            "next_commands_field": "_meta.next_commands",
        },
        "error_codes": [
            "not_found",
            "invalid_input",
            "build_mismatch",
            "rate_limited",
            "validation_failed",
            "upstream_unavailable",
            "output_validation_failed",
            "internal_error",
        ],
        "parameter_conventions": {
            "dataset": (
                "SNV/indel datasets: gnomad_r4 (GRCh38, default), gnomad_r3 (GRCh38), "
                "gnomad_r2_1 (GRCh37)."
            ),
            "reference_genome": (
                "lookup build for gene/region/clinvar/transcript tools: GRCh38 (default) or GRCh37."
            ),
            "sv_dataset": (
                "structural-variant datasets: gnomad_sv_r4 (GRCh38, default), "
                "gnomad_sv_r2_1 (GRCh37)."
            ),
            "liftover": (
                "source_genome is the build of source_variant_id; liftover converts to the "
                "other build. reference_genome is a deprecated alias for source_genome."
            ),
        },
        "contracts": {
            "resource": "gnomad://reference",
            "covers": ["error_taxonomy", "truncation_contract", "field_glossary"],
        },
        "resources": {
            "gnomad://capabilities": "this capabilities document",
            "gnomad://usage": "compact usage notes",
            "gnomad://research-use": "research-use-only notice",
            "gnomad://reference": (
                "detailed error taxonomy, truncation contract, and field/unit glossary "
                "(opt-in; keeps this capabilities doc compact)"
            ),
            "gnomad://citations": (
                "full carrier-frequency citations + assumptions, referenced by the "
                "citations_ref pointer carrier tools emit in compact mode"
            ),
        },
        "response_fields": {
            "headline": (
                "one-line plain-English answer at the top of get_variant_frequencies, "
                "get_gene_details, compute_carrier_frequency, and "
                "compute_gene_carrier_frequency; read it before parsing the tree"
            ),
            "citations_ref": (
                "pointer to gnomad://citations; carrier tools inline short citations in "
                "compact mode and full bibliographic prose with response_mode='full'"
            ),
            "next_commands": (
                "_meta.next_commands is a structured, ready-to-call list of {tool, arguments} "
                "steps present on every data tool's success and error envelope (discovery tools "
                "such as get_server_capabilities are exempt); execute the first entry to advance "
                "the workflow without guessing the next tool. The older prose "
                "next_steps array (resolve_variant_id/search_variants) is deprecated in favor "
                "of next_commands."
            ),
            "af_source": (
                "overall_af_source / af_source labels which source supplied a preferred "
                "overall AF value: exome or genome, selected by largest allele number"
            ),
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


def get_reference_resource() -> dict[str, Any]:
    """Detailed, opt-in contracts referenced from the lean capabilities doc.

    Holds the verbose error taxonomy, truncation contract, and field/unit
    glossary so the always-read capabilities payload stays compact. Surfaced at
    gnomad://reference and named from capabilities.contracts.
    """
    return {
        "error_taxonomy": {
            "envelope_fields": [
                "success",
                "error_code",
                "message",
                "retryable",
                "recovery_action",
                "fallback_tool",
                "fallback_args",
                "recovery",
            ],
            "recovery_actions": {
                "retry_backoff": "wait, then retry the SAME call",
                "reformulate_input": "fix the id/fields, same tool",
                "switch_tool": "call fallback_tool with fallback_args, then retry",
            },
            "codes": {
                "not_found": {
                    "retryable": False,
                    "when": "identifier well-formed but absent in the requested dataset",
                },
                "invalid_input": {
                    "retryable": False,
                    "when": "upstream rejected the id/query shape for this tool",
                },
                "build_mismatch": {
                    "retryable": False,
                    "when": "coordinate build != dataset build; liftover_variant first",
                },
                "rate_limited": {
                    "retryable": True,
                    "when": "HTTP 429 or local concurrency saturation",
                },
                "validation_failed": {
                    "retryable": False,
                    "when": "arguments failed schema or local guard validation",
                },
                "upstream_unavailable": {
                    "retryable": True,
                    "when": "transient gnomAD/network fault",
                },
                "output_validation_failed": {
                    "retryable": False,
                    "when": "response failed our output schema (upstream drift)",
                },
                "internal_error": {"retryable": False, "when": "unexpected server fault"},
            },
        },
        "truncation_contract": {
            "common_shape": {
                "kind": "<one of the kinds below>",
                "dropped": "count or detail of what was removed",
                "to_disable": "how to widen or remove the cap",
                "to_restore": "exact argument to recover the full payload",
                "filter": "optional: the filter that applied",
            },
            "surface_keys": [
                "truncated",
                "truncated_payload",
                "population_projection",
                "exome.truncated",
                "genome.truncated",
            ],
            "kinds": [
                "contributing_variants",
                "coverage_bins",
                "gene_payload",
                "gene_variants",
                "heteroplasmy_zeros",
                "pathogenic_clinvar",
                "populations",
                "region_payload",
                "region_span",
                "search_results",
                "structural_variant",
                "structural_variants",
                "submissions",
                "transcript_consequences",
            ],
        },
        "field_glossary": {
            "af": "allele frequency = ac / an, scale 0-1",
            "ac": "allele count, integer",
            "an": "allele number (called alleles), integer",
            "homozygote_count": "integer",
            "carrier_frequency": "scale 0-1; carrier_one_in = round(1 / carrier_frequency)",
            "coverage.mean": "mean read depth, fold (x)",
            "over_20": "fraction of samples with depth >= 20x, scale 0-1",
            "over_30": "fraction of samples with depth >= 30x, scale 0-1",
            "structural_variant.length": "base pairs (bp)",
            "pos": "1-based genomic coordinate",
            "region": "CHROM-START-STOP, 1-based inclusive",
        },
        "research_use_only": True,
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
