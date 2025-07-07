#!/usr/bin/env python
"""FastAPI server for gnomAD variant data."""
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware

from gnomad_mcp.api import UnifiedGnomadClient, DataNotFoundError, GnomadApiError
from gnomad_mcp.services import UnifiedFrequencyService
from gnomad_mcp.config import settings

# Configure logging
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = logging.getLogger(__name__)

# --- Dependency Setup ---
# Global instances to be shared across the application
api_client: UnifiedGnomadClient = None
frequency_service: UnifiedFrequencyService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown."""
    global api_client, frequency_service

    # Startup
    logger.info("Starting gnomAD server...")
    logger.info(
        f"Cache configuration: size={settings.CACHE_SIZE}, TTL={settings.CACHE_TTL_MINUTES}min"
    )

    api_client = UnifiedGnomadClient()
    frequency_service = UnifiedFrequencyService(
        client=api_client,
        cache_size=settings.CACHE_SIZE,
        cache_ttl_minutes=settings.CACHE_TTL_MINUTES,
    )

    # Set the service in the dependencies module
    from gnomad_mcp.api.routes.dependencies import set_service

    set_service(frequency_service)

    yield

    # Shutdown
    logger.info("Shutting down gnomAD server...")
    await frequency_service.close()


# --- FastAPI App ---
app = FastAPI(
    title="gnomAD Data Server",
    description=(
        "Comprehensive API for accessing gnomAD genomic data including variants, "
        "genes, ClinVar annotations, structural variants, and more. "
        "For MCP interface, see mcp_server.py"
    ),
    version="3.0.0",
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

# Import and include all routers
from gnomad_mcp.api.routes import (
    variant_router,
    gene_router,
    clinvar_router,
    structural_variant_router,
    mitochondrial_router,
    region_router,
    transcript_router,
    search_router,
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


@app.get("/")
async def root() -> Dict[str, Any]:
    """Root endpoint providing API information."""
    return {
        "message": "gnomAD Data Server",
        "version": "3.0.0",
        "endpoints": {
            "api_docs": "/docs",
            "health": "/health",
            "cache_stats": "/cache/stats",
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


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/cache/stats", tags=["Monitoring"])
async def cache_stats() -> Dict[str, Any]:
    """Get cache statistics for monitoring."""
    return frequency_service.get_cache_stats()


@app.post("/cache/clear", tags=["Monitoring"])
async def clear_cache() -> Dict[str, str]:
    """Clear the variant cache."""
    frequency_service.clear_cache()
    return {"status": "cache_cleared"}


# --- Main entry point ---
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable auto-reload during development
        log_level="info",
    )
