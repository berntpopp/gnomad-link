"""Hand-authored FastMCP facade for gnomAD Link."""

from __future__ import annotations

from collections.abc import Callable

from fastmcp import FastMCP

from gnomad_link.mcp.resources import RESEARCH_USE_NOTICE
from gnomad_link.mcp.tools import register_gnomad_tools
from gnomad_link.services import FrequencyService

_INSTRUCTIONS = (
    "gnomAD Link grounds population-genetics work in gnomAD datasets.\n"
    "- Variant frequency: get_variant_frequencies for CHROM-POS-REF-ALT; "
    "resolve_variant_id first for rsIDs or loose text.\n"
    "- Clinical annotation: pair get_clinvar_variant_details with "
    "get_variant_frequencies.\n"
    "- Gene constraint: search_genes then get_gene_details.\n"
    "- Coordinates: liftover_variant converts between GRCh37 and GRCh38.\n"
    "- Special variants: get_structural_variant for SVs; "
    "get_mitochondrial_variant for M-POS-REF-ALT.\n"
    "- Region scans: get_region with include_clinvar/include_genes; "
    "cap span at 100kb.\n"
    "- Datasets: gnomad_r2_1 is GRCh37; gnomad_r3 and gnomad_r4 are GRCh38; "
    "gnomad_r4 is default.\n"
    "- Compact defaults trim subcohort and zero-AC populations; pass "
    "include_subcohorts=True or response_mode='full' for raw payloads.\n"
    "- Discovery: call get_server_capabilities or read gnomad://capabilities. "
    f"{RESEARCH_USE_NOTICE}"
)


def create_gnomad_mcp(
    *,
    service_factory: Callable[[], FrequencyService],
) -> FastMCP:
    """Build the gnomAD Link MCP server.

    `service_factory` is a lazy callable so HTTP mode can defer to
    `app.state.frequency_service` and stdio mode can hold a directly
    constructed instance.
    """

    mcp = FastMCP(
        name="gnomad-link",
        instructions=_INSTRUCTIONS,
        mask_error_details=True,
    )
    register_gnomad_tools(mcp, service_factory=service_factory)
    return mcp
