"""Transcript-related API routes."""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Query, Path, Depends
from gnomad_mcp.models import ReferenceGenome
from gnomad_mcp.api import DataNotFoundError
from gnomad_mcp.services import UnifiedFrequencyService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transcript", tags=["Transcripts"])

from .dependencies import get_service


@router.get(
    "/{transcript_id}",
    summary="Get transcript information",
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
    service: UnifiedFrequencyService = Depends(get_service),
) -> Dict[str, Any]:
    """Get transcript information including exons and expression data."""
    try:
        result = await service.client.get_transcript(transcript_id, reference_genome)
        return result
    except DataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting transcript: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
