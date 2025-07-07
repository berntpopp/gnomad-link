"""Structural variant API routes."""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Path, Query, Depends
from gnomad_mcp.models import StructuralVariantDataset
from gnomad_mcp.api import DataNotFoundError
from gnomad_mcp.services import UnifiedFrequencyService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/structural-variant", tags=["Structural Variants"])

from .dependencies import get_service


@router.get(
    "/{variant_id}",
    summary="Get structural variant data",
    responses={
        404: {"description": "Variant not found"},
        400: {"description": "Invalid input"},
    },
)
async def get_structural_variant(
    variant_id: str = Path(..., description="Structural variant identifier"),
    dataset: StructuralVariantDataset = Query(
        default=StructuralVariantDataset.GNOMAD_SV_R4,
        description="gnomAD structural variant dataset",
    ),
    service: UnifiedFrequencyService = Depends(get_service),
) -> Dict[str, Any]:
    """Get structural variant information."""
    try:
        result = await service.client.get_structural_variant(variant_id, dataset)
        return result
    except DataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting structural variant: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")