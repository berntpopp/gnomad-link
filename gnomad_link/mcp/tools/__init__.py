"""Tool registration entry points for the gnomAD Link MCP facade."""

from __future__ import annotations

from collections.abc import Callable

from fastmcp import FastMCP

from gnomad_link.services import FrequencyService

from gnomad_link.mcp.tools.clinvar import register_clinvar_tools
from gnomad_link.mcp.tools.coordinates import register_coordinate_tools
from gnomad_link.mcp.tools.genes import register_gene_tools
from gnomad_link.mcp.tools.metadata import register_metadata_tools
from gnomad_link.mcp.tools.search import register_search_tools
from gnomad_link.mcp.tools.specialty import register_specialty_tools
from gnomad_link.mcp.tools.variants import register_variant_tools


def register_gnomad_tools(
    mcp: FastMCP,
    *,
    service_factory: Callable[[], FrequencyService],
) -> None:
    register_metadata_tools(mcp)
    register_variant_tools(mcp, service_factory=service_factory)
    register_gene_tools(mcp, service_factory=service_factory)
    register_clinvar_tools(mcp, service_factory=service_factory)
    register_coordinate_tools(mcp, service_factory=service_factory)
    register_specialty_tools(mcp, service_factory=service_factory)
    register_search_tools(mcp, service_factory=service_factory)
