#!/usr/bin/env python
"""Unified FastAPI and MCP server for gnomAD variant data.

Single entry point for both REST API and Language Model tools.
"""
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP

# Import services and models
from gnomad_mcp.api.client import UnifiedGnomadClient
from gnomad_mcp.api.routes import (
    clinvar_router,
    gene_router,
    mitochondrial_router,
    region_router,
    search_router,
    structural_variant_router,
    transcript_router,
    variant_router,
)
from gnomad_mcp.api.routes.dependencies import get_service
from gnomad_mcp.config import settings
from gnomad_mcp.services.frequency_service import FrequencyService

# Configure logging
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = logging.getLogger(__name__)


# --- Application Lifespan (Startup & Shutdown) ---
# Based on FastAPI documentation for managing shared resources.
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown."""
    logger.info("Starting gnomAD Unified Server...")
    logger.info(
        f"Cache configuration: size={settings.CACHE_SIZE}, "
        f"TTL={settings.CACHE_TTL_MINUTES}min"
    )

    # Instantiate services ONCE and store them in the application's shared state.
    api_client = UnifiedGnomadClient()
    app.state.frequency_service = FrequencyService(
        client=api_client,
        cache_size=settings.CACHE_SIZE,
        cache_ttl_minutes=settings.CACHE_TTL_MINUTES,
    )

    yield  # The server is now running.

    logger.info("Shutting down gnomAD Unified Server...")
    await app.state.frequency_service.close()


# --- FastAPI App Definition ---
app = FastAPI(
    title="gnomAD Unified Data Server",
    description=(
        "Provides a comprehensive REST API and a focused MCP toolset for gnomAD. "
        "Access REST API at / and MCP tools at /mcp"
    ),
    version="4.0.0",
    lifespan=lifespan,
)

# Add CORS middleware for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include all routers
app.include_router(variant_router)
app.include_router(gene_router)
app.include_router(clinvar_router)
app.include_router(structural_variant_router)
app.include_router(mitochondrial_router)
app.include_router(region_router)
app.include_router(transcript_router)
app.include_router(search_router)


# --- Initialize services for MCP ---
# Since MCP doesn't trigger the lifespan event, we need to initialize services manually
if not hasattr(app.state, "frequency_service"):
    api_client = UnifiedGnomadClient()
    app.state.frequency_service = FrequencyService(
        client=api_client,
        cache_size=settings.CACHE_SIZE,
        cache_ttl_minutes=settings.CACHE_TTL_MINUTES,
    )

# --- Create MCP server from FastAPI app ---
# Use from_fastapi without route_maps to avoid AttributeError
mcp = FastMCP.from_fastapi(app=app, name="gnomAD Tool Server")


# --- Root and Health Endpoints ---
@app.get("/", operation_id="get_root")
async def root() -> dict[str, Any]:
    """Root endpoint providing API information."""
    return {
        "message": "gnomAD Unified Data Server",
        "version": "4.0.0",
        "interfaces": {
            "rest_api": {
                "docs": "/docs",
                "health": "/health",
                "cache_stats": "/cache/stats",
            },
            "mcp_tools": {
                "note": "MCP tools are defined via FastMCP integration",
                "tools": ["get_variant_allele_frequency", "get_gene_summary"],
            },
        },
        "endpoints": {
            "variants": {
                "lookup": "/variant/{variant_id}",
                "details": "/variant/details/{variant_id}",
                "search": "/search/variant",
            },
            "genes": {
                "lookup": "/gene/",
                "search": "/search/gene",
            },
            "clinvar": {
                "variant": "/clinvar/variant/{variant_id}",
            },
            "structural_variants": {
                "lookup": "/structural-variant/{variant_id}",
            },
            "mitochondrial_variants": {
                "lookup": "/mitochondrial-variant/{variant_id}",
            },
            "regions": {
                "query": "/region/",
            },
            "transcripts": {
                "lookup": "/transcript/{transcript_id}",
            },
        },
    }


@app.get("/health", operation_id="health_check")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/cache/stats", tags=["Monitoring"], operation_id="get_cache_stats")
async def cache_stats(
    service: FrequencyService = Depends(get_service),
) -> dict[str, Any]:
    """Get cache statistics for monitoring."""
    return service.get_cache_stats()


@app.post("/cache/clear", tags=["Monitoring"], operation_id="clear_cache")
async def clear_cache(
    service: FrequencyService = Depends(get_service),
) -> dict[str, str]:
    """Clear the variant cache."""
    service.clear_cache()
    return {"status": "cache_cleared"}


# --- Main Entry Point (for `uvicorn server:app`) ---
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable auto-reload during development
        log_level="info",
    )
