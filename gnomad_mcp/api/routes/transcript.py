"""Transcript-related API routes."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from gnomad_mcp.api import DataNotFoundError
from gnomad_mcp.models import ReferenceGenome
from gnomad_mcp.services import FrequencyService

from .dependencies import get_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transcript", tags=["Transcripts"])


@router.get(
    "/{transcript_id}",
    summary="Get transcript information",
    operation_id="get_transcript_details",
    responses={
        404: {"description": "Transcript not found"},
        400: {"description": "Invalid input"},
    },
)
async def get_transcript(
    transcript_id: str = Path(..., description="Ensembl transcript ID"),
    reference_genome: ReferenceGenome = Query(
        default=ReferenceGenome.GRCH38,
        description="Reference genome to use",
    ),
    service: FrequencyService = Depends(get_service),
) -> dict[str, Any]:
    """Get transcript information including exons and expression data."""
    try:
        result = await service.client.get_transcript(transcript_id, reference_genome)
        return result
    except DataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting transcript: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
