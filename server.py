#!/usr/bin/env python
"""FastAPI server for gnomAD variant data."""
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware

from gnomad_mcp.api import GnomadApiClient, VariantNotFoundError, GnomadApiError
from gnomad_mcp.services import FrequencyService
from gnomad_mcp.models import VariantFrequencyResponse
from gnomad_mcp.config import settings

# Configure logging
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = logging.getLogger(__name__)

# --- Dependency Setup ---
# Global instances to be shared across the application
api_client: GnomadApiClient = None
frequency_service: FrequencyService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown."""
    global api_client, frequency_service

    # Startup
    logger.info("Starting gnomAD server...")
    logger.info(
        f"Cache configuration: size={settings.CACHE_SIZE}, TTL={settings.CACHE_TTL_MINUTES}min"
    )

    api_client = GnomadApiClient()
    frequency_service = FrequencyService(
        client=api_client,
        cache_size=settings.CACHE_SIZE,
        cache_ttl_minutes=settings.CACHE_TTL_MINUTES,
    )

    yield

    # Shutdown
    logger.info("Shutting down gnomAD server...")
    await frequency_service.close()


# --- FastAPI App ---
app = FastAPI(
    title="gnomAD Data Server",
    description=(
        "Provides allele frequency data from gnomAD via a REST API. "
        "For MCP interface, see mcp_server.py"
    ),
    version="2.0.0",
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


@app.get("/")
async def root() -> Dict[str, Any]:
    """Root endpoint providing API information."""
    return {
        "message": "gnomAD Data Server",
        "version": "2.0.0",
        "endpoints": {
            "api_docs": "/docs",
            "variant_lookup": "/variant/{dataset}/{variant_id}",
            "health": "/health",
            "cache_stats": "/cache/stats",
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


@app.get(
    "/variant/{dataset}/{variant_id}",
    response_model=VariantFrequencyResponse,
    tags=["Variants"],
    summary="Get variant frequency data",
    responses={
        404: {"description": "Variant not found"},
        400: {"description": "Invalid input"},
        502: {"description": "Upstream API error"},
        500: {"description": "Internal server error"},
    },
)
async def get_variant_fastapi(
    variant_id: str = Path(
        ...,
        description="Variant identifier (e.g., '1-55039447-G-T')",
        examples=["1-55039447-G-T"],
        pattern=r"^[^'\"]+$",  # No quotes allowed
    ),
    dataset: str = Path(
        ...,
        description="gnomAD dataset ID (e.g., 'gnomad_r4')",
        examples=["gnomad_r4"],
        pattern=r"^gnomad_r\d+(_\w+)?$",  # Match gnomad_r2, gnomad_r3, gnomad_r4, etc
    ),
) -> VariantFrequencyResponse:
    """
    Retrieve allele frequency data for a specific variant.

    This endpoint queries the gnomAD database and returns population-specific
    allele frequencies for both exome and genome sequencing data.
    """
    try:
        return await frequency_service.get_variant_frequencies(variant_id, dataset)
    except VariantNotFoundError as e:
        logger.warning(f"Variant not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        logger.warning(f"Invalid input: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except GnomadApiError as e:
        logger.error(f"API error: {e}")
        raise HTTPException(
            status_code=502, detail="Error communicating with gnomAD API"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal server error occurred")


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
