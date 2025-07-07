#!/usr/bin/env python
"""
MCP server that introspects and serves the FastAPI application to language models.

This file creates an MCP interface from the existing FastAPI app, providing
zero-duplication access to all API functionality for AI assistants.
"""

import logging
import sys

from fastmcp import FastMCP
from fastmcp.server.openapi import MCPType, RouteMap

# Import the FastAPI app instance from the main server file
from server import app

# Configure logging - only show warnings and errors to avoid interfering with STDIO
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)

# Suppress verbose logging from fastmcp libraries
logging.getLogger("fastmcp").setLevel(logging.WARNING)
logging.getLogger("fastmcp.utilities.openapi").setLevel(logging.WARNING)

# --- MCP Server Customization ---

# Define custom names for tools to make them more LLM-friendly
# The key is the 'operation_id' from the FastAPI route
MCP_CUSTOM_NAMES = {
    # Variant endpoints
    "get_variant_frequency_data": "get_variant_frequencies",
    "search_variants": "search_variants",
    "get_variant_by_position": "get_variant_by_position",

    # Gene endpoints
    "get_gene_details": "get_gene_details",
    "search_genes": "search_genes",

    # Transcript endpoints
    "search_transcripts": "search_transcripts",
    "get_transcript_exons": "get_transcript_exons",

    # Structural variant endpoints
    "search_structural_variants": "get_structural_variants",

    # ClinVar endpoints
    "search_clinvar_variants": "search_clinvar_variants",
    "get_clinvar_variant": "get_clinvar_variant_details",

    # Coverage endpoints
    "get_gene_coverage": "get_gene_coverage",
    "get_transcript_coverage": "get_transcript_coverage",
}

# Define routing rules to exclude certain endpoints from MCP
MCP_ROUTE_MAPS = [
    # Exclude health and monitoring endpoints
    RouteMap(pattern=r"^/api/health$", mcp_type=MCPType.EXCLUDE),
    RouteMap(pattern=r"^/health$", mcp_type=MCPType.EXCLUDE),

    # Exclude cache management endpoints
    RouteMap(pattern=r"^/api/cache/.*$", mcp_type=MCPType.EXCLUDE),

    # Exclude root and docs endpoints
    RouteMap(pattern=r"^/$", mcp_type=MCPType.EXCLUDE),
    RouteMap(pattern=r"^/docs$", mcp_type=MCPType.EXCLUDE),
    RouteMap(pattern=r"^/openapi.json$", mcp_type=MCPType.EXCLUDE),
    RouteMap(pattern=r"^/redoc$", mcp_type=MCPType.EXCLUDE),
]

# --- Create the MCP Server from the FastAPI App ---

# Remove this logging line as it might interfere with STDIO

# Create MCP server by introspecting the FastAPI app
mcp = FastMCP.from_fastapi(
    app=app,
    name="gnomAD MCP Server",
    mcp_names=MCP_CUSTOM_NAMES,
    route_maps=MCP_ROUTE_MAPS,
)

# Server metadata is set via the FastAPI app's metadata

if __name__ == "__main__":
    # Run the MCP server in STDIO mode
    mcp.run()
