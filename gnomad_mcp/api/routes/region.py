"""Region-based API routes for querying genomic regions.

This module provides endpoints for retrieving variants and genes within
specified genomic coordinates.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from gnomad_mcp.models import GnomadDataset
from gnomad_mcp.services import FrequencyService

from .dependencies import get_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/region", tags=["Regions"])


@router.get(
    "/",
    summary="Get variants and genes in a genomic region",
    description="Query all variants and overlapping genes within specified genomic coordinates.",
    operation_id="get_region",
    responses={
        200: {
            "description": "Region data retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "region": {
                            "chrom": "19",
                            "start": 11078371,
                            "stop": 11144910,
                            "reference_genome": "GRCh38",
                        },
                        "genes": [
                            {
                                "gene_id": "ENSG00000105641",
                                "symbol": "LDLR",
                                "start": 11089463,
                                "stop": 11133830,
                                "strand": "+",
                            }
                        ],
                        "variant_count": 2847,
                        "variants": [
                            {
                                "variant_id": "19-11089479-G-A",
                                "rsid": "rs688",
                                "consequence": "5_prime_UTR_variant",
                                "gene_symbol": "LDLR",
                                "af": 0.467,
                            }
                        ],
                    }
                }
            },
        },
        400: {"description": "Invalid coordinates (stop must be > start)"},
        500: {"description": "Internal server error"},
    },
)
async def get_region(
    chrom: str = Query(
        ...,
        description="Chromosome",
        pattern=r"^(chr)?([1-9]|1[0-9]|2[0-2]|X|Y|M|MT)$",
        openapi_examples={
            "structural_variant": {
                "summary": "Structural variant region",
                "description": "Chromosome for structural variant region example",
                "value": "19",
            },
            "cnv": {
                "summary": "Copy number variant region",
                "description": "Chromosome for CNV region example",
                "value": "1",
            },
        },
    ),
    start: int = Query(
        ...,
        description="Start position (1-based)",
        ge=1,
        openapi_examples={
            "structural_variant": {
                "summary": "SV region start",
                "description": "Start position for structural variant region",
                "value": 11078371,
            },
            "cnv": {
                "summary": "CNV region start",
                "description": "Start position for copy number variant region",
                "value": 55039447,
            },
        },
    ),
    stop: int = Query(
        ...,
        description="Stop position (1-based, inclusive)",
        ge=1,
        openapi_examples={
            "structural_variant": {
                "summary": "SV region stop",
                "description": "Stop position for structural variant region",
                "value": 11144910,
            },
            "cnv": {
                "summary": "CNV region stop",
                "description": "Stop position for copy number variant region",
                "value": 55064852,
            },
        },
    ),
    dataset: GnomadDataset = Query(
        default=GnomadDataset.GNOMAD_R4,
        description="gnomAD dataset version to query",
    ),
    service: FrequencyService = Depends(get_service),
) -> dict[str, Any]:
    """Get all variants and genes within a genomic region.

    This endpoint returns all variants and genes that overlap with the
    specified genomic coordinates. Results include:
    - All variants within the region with basic annotations
    - Genes that overlap the region (even partially)
    - Summary statistics about the region

    The maximum region size allowed is typically 1 Mb.

    Args:
        chrom: Chromosome (1-22, X, Y, M/MT)
        start: Start position (1-based, inclusive)
        stop: Stop position (1-based, inclusive)
        dataset: gnomAD dataset version (v2, v3, or v4)
        service: Injected frequency service

    Returns:
        Dictionary containing region info, variants, and genes

    Raises:
        HTTPException(400): Invalid coordinates
        HTTPException(500): Internal server error
    """
    if stop <= start:
        raise HTTPException(
            status_code=400, detail="Stop position must be greater than start position"
        )

    try:
        result = await service.client.get_region(chrom, start, stop, dataset)
        return result
    except Exception as e:
        logger.error(f"Error getting region: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
