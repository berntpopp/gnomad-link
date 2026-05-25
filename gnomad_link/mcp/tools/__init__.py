"""Tool registration entry points for the gnomAD Link MCP facade."""

from __future__ import annotations

from collections.abc import Callable

from fastmcp import FastMCP

from gnomad_link.services import FrequencyService

from gnomad_link.mcp.tools.genes import register_gene_tools
from gnomad_link.mcp.tools.metadata import register_metadata_tools
from gnomad_link.mcp.tools.variants import register_variant_tools


def register_gnomad_tools(
    mcp: FastMCP,
    *,
    service_factory: Callable[[], FrequencyService],
) -> None:
    register_metadata_tools(mcp)
    register_variant_tools(mcp, service_factory=service_factory)
    register_gene_tools(mcp, service_factory=service_factory)
    # Remaining data tool registrations are added in Task 8.
