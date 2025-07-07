"""Variant-related API routes."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from gnomad_mcp.api import DataNotFoundError, GnomadApiError
from gnomad_mcp.models import GnomadDataset, VariantFrequencyResponse
from gnomad_mcp.services import FrequencyService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/variant", tags=["Variants"])

from .dependencies import get_service


@router.get(
    "/{variant_id}",
    response_model=VariantFrequencyResponse,
    summary="Get variant frequency data",
    responses={
        404: {"description": "Variant not found"},
        400: {"description": "Invalid input"},
        502: {"description": "Upstream API error"},
        500: {"description": "Internal server error"},
    },
)
async def get_variant(
    variant_id: str = Path(
        ...,
        description="Variant identifier (e.g., '1-55039447-G-T')",
        examples=["1-55039447-G-T"],
        pattern=r"^[^'\"]+$",
    ),
    dataset: GnomadDataset = Query(
        default=GnomadDataset.GNOMAD_R4,
        description="gnomAD dataset to query",
    ),
    service: FrequencyService = Depends(get_service),
) -> VariantFrequencyResponse:
    """Retrieve allele frequency data for a specific variant."""
    try:
        return await service.get_variant_frequencies(variant_id, dataset)
    except DataNotFoundError as e:
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


@router.get(
    "/details/{variant_id}",
    summary="Get detailed variant information",
    responses={
        404: {"description": "Variant not found"},
        400: {"description": "Invalid input"},
    },
)
async def get_variant_details(
    variant_id: str = Path(..., description="Variant identifier"),
    dataset: GnomadDataset = Query(
        default=GnomadDataset.GNOMAD_R4,
        description="gnomAD dataset to query",
    ),
    service: FrequencyService = Depends(get_service),
) -> dict[str, Any]:
    """Get complete variant details including annotations."""
    try:
        result = await service.client.get_variant(variant_id, dataset)
        return result
    except DataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting variant details: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
