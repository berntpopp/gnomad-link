"""Hand-authored FastMCP facade for gnomAD Link."""

from __future__ import annotations

from collections.abc import Callable

from fastmcp import FastMCP

from gnomad_link import __version__
from gnomad_link.mcp.errors import install_validation_error_handler
from gnomad_link.mcp.notfound_guard import (
    NotFoundGuard,
    install_notfound_log_filter,
    install_protocol_error_handler,
)
from gnomad_link.mcp.output_validation import install_output_validation_error_handler
from gnomad_link.mcp.prompts import register_workflow_prompts
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
    "- Coordinates: compute_variant_liftover converts between GRCh37 and GRCh38.\n"
    "- Special variants: get_structural_variant for SVs; "
    "get_mitochondrial_variant for M-POS-REF-ALT.\n"
    "- Region scans: get_region with include_clinvar/include_genes; "
    "cap span at 100kb.\n"
    "- Datasets: gnomad_r2_1 is GRCh37; gnomad_r3 and gnomad_r4 are GRCh38; "
    "gnomad_r4 is default.\n"
    "- Compact defaults trim subcohort and zero-AC populations; pass "
    "include_subcohorts=True or response_mode='full' for raw payloads.\n"
    "- Chaining: every response carries _meta.next_commands, a ready-to-call list "
    "of {tool, arguments} next steps (on success and error); execute the first "
    "entry to advance without guessing the next tool.\n"
    "- Discovery: call get_server_capabilities or read gnomad://capabilities; "
    "gnomad://reference holds the error taxonomy, truncation contract, and field "
    "glossary. "
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
        version=__version__,
        instructions=_INSTRUCTIONS,
        mask_error_details=True,
        dereference_schemas=False,
    )
    # Guard the FastMCP-core not-found reflection surface: core echoes the
    # caller's OWN requested tool name / resource URI / prompt name (with any
    # control/zero-width/bidi/NUL code points) to the caller and to logs BEFORE
    # backend middleware runs. NotFoundGuard preflights the tool NAME (unknown ->
    # fixed name-free envelope) and fixes the on_read_resource boundary; add it
    # FIRST so it is the OUTERMOST middleware. See notfound_guard.py.
    mcp.add_middleware(NotFoundGuard())
    register_gnomad_tools(mcp, service_factory=service_factory)
    register_workflow_prompts(mcp)
    install_validation_error_handler(mcp)
    install_output_validation_error_handler(mcp)
    # Layer 3: install the protocol-handler backstop AFTER every tool/resource/
    # prompt is registered and AFTER the output-schema handler, so it is the
    # outermost wrapper on the raw CallTool/ReadResource/GetPrompt handlers. It
    # catches the unknown-tool *return* path and any resource/prompt dispatch
    # error that would echo the requested name/URI (the only layer covering the
    # unknown-prompt surface).
    install_protocol_error_handler(mcp)
    # Layer 5: scrub FastMCP-core / MCP-SDK validation logs that would echo the
    # caller-supplied name/URI (idempotent; process-global).
    install_notfound_log_filter()
    return mcp
