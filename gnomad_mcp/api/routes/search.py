"""Search API routes."""

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends
from gnomad_mcp.models import GeneSearchResult, ReferenceGenome, GnomadDataset
from gnomad_mcp.api import DataNotFoundError
from gnomad_mcp.services import UnifiedFrequencyService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["Search"])

from .dependencies import get_service


@router.get(
    "/gene",
    response_model=List[GeneSearchResult],
    summary="Search for genes",
    responses={
        400: {"description": "Invalid input"},
    },
)
async def search_genes(
    query: str = Query(
        ..., description="Search query (gene symbol or ID)", min_length=2
    ),
    reference_genome: ReferenceGenome = Query(
        default=ReferenceGenome.GRCH38,
        description="Reference genome to use",
    ),
    service: UnifiedFrequencyService = Depends(get_service),
) -> List[GeneSearchResult]:
    """Search for genes by symbol or Ensembl ID."""
    try:
        results = await service.client.search_genes(query, reference_genome)
        return [GeneSearchResult(**r) for r in results]
    except Exception as e:
        logger.error(f"Error searching genes: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/variant",
    summary="Search for variants",
    responses={
        400: {"description": "Invalid input"},
    },
)
async def search_variants(
    query: str = Query(..., description="Search query", min_length=3),
    dataset: GnomadDataset = Query(
        default=GnomadDataset.GNOMAD_R4,
        description="gnomAD dataset to query",
    ),
    service: UnifiedFrequencyService = Depends(get_service),
) -> List[Dict[str, Any]]:
    """Search for variants by ID or rsID."""
    try:
        results = await service.client.search_variants(query, dataset)
        return results
    except Exception as e:
        logger.error(f"Error searching variants: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
