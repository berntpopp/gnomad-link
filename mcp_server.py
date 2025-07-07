#!/usr/bin/env python
"""MCP server for gnomAD variant data."""
import asyncio
import logging
from fastmcp import FastMCP

from gnomad_mcp.api import GnomadApiClient
from gnomad_mcp.services import FrequencyService
from gnomad_mcp.models import VariantFrequencyResponse, GnomadDataset
from gnomad_mcp.config import settings

# Configure logging
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP("gnomAD MCP Server")

# Initialize dependencies
api_client = None
frequency_service = None


async def startup():
    """Initialize services on startup."""
    global api_client, frequency_service
    logger.info("Starting gnomAD MCP server...")
    logger.info(
        f"Cache configuration: size={settings.CACHE_SIZE}, TTL={settings.CACHE_TTL_MINUTES}min"
    )

    api_client = GnomadApiClient()
    frequency_service = FrequencyService(
        client=api_client,
        cache_size=settings.CACHE_SIZE,
        cache_ttl_minutes=settings.CACHE_TTL_MINUTES,
    )


async def shutdown():
    """Cleanup on shutdown."""
    logger.info("Shutting down gnomAD MCP server...")
    if frequency_service:
        await frequency_service.close()


@mcp.tool
async def get_variant_allele_frequency(
    variant_id: str,
    dataset: str = "gnomad_r4",
) -> dict:
    """
    Retrieve population allele frequency data for a genetic variant from gnomAD.

    This tool queries the gnomAD (Genome Aggregation Database) to get detailed
    population-specific allele frequencies for a given variant. The data includes
    frequencies from both exome and genome sequencing projects.

    Args:
        variant_id: The variant identifier in the format "chromosome-position-reference-alternate"
                   (e.g., "1-55039447-G-T" for a G>T variant at position 55039447 on chromosome 1)
        dataset: The gnomAD dataset to query. Common values include:
                - "gnomad_r4": Latest release (v4) [DEFAULT]
                - "gnomad_r3": Previous release (v3)
                - "gnomad_r2_1": Legacy release (v2.1)

    Returns:
        A structured object containing:
        - variant_id: The queried variant
        - dataset: The dataset used
        - exome: Population frequencies from exome sequencing (if available)
        - genome: Population frequencies from genome sequencing (if available)

        Each data source includes population-specific breakdowns with:
        - allele_count: Number of alternate alleles observed
        - allele_number: Total number of alleles assessed
        - homozygote_count: Number of homozygous individuals

    Example:
        To look up the frequency of variant rs1234567 (1-55039447-G-T) in gnomAD v4:
        ```
        result = await get_variant_allele_frequency("1-55039447-G-T", "gnomad_r4")
        ```
    """
    # Ensure services are initialized
    if not frequency_service:
        await startup()

    try:
        result = await frequency_service.get_variant_frequencies(variant_id, dataset)
        # Convert Pydantic model to dict for MCP
        return result.model_dump()
    except Exception as e:
        # MCP expects tools to return results or raise exceptions
        raise Exception(f"Error fetching variant data: {str(e)}")


@mcp.tool
async def get_cache_stats() -> dict:
    """
    Get cache statistics for the gnomAD MCP server.

    Returns cache performance metrics including hits, misses, and hit rate.
    """
    if not frequency_service:
        await startup()

    return frequency_service.get_cache_stats()


if __name__ == "__main__":
    # Run the MCP server with STDIO transport (default)
    # This allows it to work with MCP clients like Claude Desktop
    asyncio.run(startup())
    try:
        mcp.run()
    finally:
        asyncio.run(shutdown())
