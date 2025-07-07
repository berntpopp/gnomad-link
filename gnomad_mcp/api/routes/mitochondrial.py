"""Mitochondrial variant API routes."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from gnomad_mcp.api import DataNotFoundError
from gnomad_mcp.models import GnomadDataset
from gnomad_mcp.services import FrequencyService

from .dependencies import get_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mitochondrial-variant", tags=["Mitochondrial Variants"])


@router.get(
    "/{variant_id}",
    summary="Get mitochondrial variant data",
    operation_id="get_mitochondrial_variant",
    responses={
        404: {"description": "Variant not found"},
        400: {"description": "Invalid input"},
    },
)
async def get_mitochondrial_variant(
    variant_id: str = Path(..., description="Mitochondrial variant identifier"),
    dataset: GnomadDataset = Query(
        default=GnomadDataset.GNOMAD_R4,
        description="gnomAD dataset to query",
    ),
    service: FrequencyService = Depends(get_service),
) -> dict[str, Any]:
    """Get mitochondrial variant information with heteroplasmy data."""
    try:
        result = await service.client.get_mitochondrial_variant(variant_id, dataset)
        return result
    except DataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting mitochondrial variant: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
