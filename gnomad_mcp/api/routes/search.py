"""Search API routes."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from gnomad_mcp.models import GeneSearchResult, GnomadDataset, ReferenceGenome
from gnomad_mcp.services import FrequencyService

from .dependencies import get_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["Search"])


@router.get(
    "/gene",
    response_model=list[GeneSearchResult],
    summary="Search for genes",
    operation_id="search_genes",
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
    service: FrequencyService = Depends(get_service),
) -> list[GeneSearchResult]:
    """Search for genes by symbol or Ensembl ID."""
    try:
        results = await service.client.search_genes(query, reference_genome)
        return [GeneSearchResult(**r) for r in results]
    except Exception as e:
        logger.error(f"Error searching genes: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get(
    "/variant",
    summary="Search for variants",
    operation_id="search_variants",
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
    service: FrequencyService = Depends(get_service),
) -> list[dict[str, Any]]:
    """Search for variants by ID or rsID."""
    try:
        results = await service.client.search_variants(query, dataset)
        return results
    except Exception as e:
        logger.error(f"Error searching variants: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
