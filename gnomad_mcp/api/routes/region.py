"""Region-based API routes."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from gnomad_mcp.models import GnomadDataset
from gnomad_mcp.services import FrequencyService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/region", tags=["Regions"])

from .dependencies import get_service


@router.get(
    "/",
    summary="Get variants and genes in a genomic region",
    responses={
        400: {"description": "Invalid input"},
    },
)
async def get_region(
    chrom: str = Query(..., description="Chromosome (e.g., '1', 'X')"),
    start: int = Query(..., description="Start position", ge=1),
    stop: int = Query(..., description="Stop position", ge=1),
    dataset: GnomadDataset = Query(
        default=GnomadDataset.GNOMAD_R4,
        description="gnomAD dataset to query",
    ),
    service: FrequencyService = Depends(get_service),
) -> dict[str, Any]:
    """Get all variants and genes within a genomic region."""
    if stop <= start:
        raise HTTPException(
            status_code=400, detail="Stop position must be greater than start position"
        )

    try:
        result = await service.client.get_region(chrom, start, stop, dataset)
        return result
    except Exception as e:
        logger.error(f"Error getting region: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
