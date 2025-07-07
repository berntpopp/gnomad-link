"""ClinVar-related API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from gnomad_mcp.api import DataNotFoundError
from gnomad_mcp.models import ClinVarVariant, ReferenceGenome
from gnomad_mcp.services import FrequencyService

from .dependencies import get_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/clinvar", tags=["ClinVar"])


@router.get(
    "/variant/{variant_id}",
    response_model=ClinVarVariant,
    summary="Get ClinVar data for a variant",
    operation_id="get_clinvar_variant",
    responses={
        404: {"description": "Variant not found"},
        400: {"description": "Invalid input"},
    },
)
async def get_clinvar_variant(
    variant_id: str,
    reference_genome: ReferenceGenome = Query(
        default=ReferenceGenome.GRCH38,
        description="Reference genome to use",
    ),
    service: FrequencyService = Depends(get_service),
) -> ClinVarVariant:
    """Get ClinVar clinical significance data for a variant."""
    try:
        result = await service.client.get_clinvar_variant(variant_id, reference_genome)
        return ClinVarVariant(**result.get("clinvar_variant", result))
    except DataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting ClinVar variant: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
