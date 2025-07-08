"""Region-based API routes for querying genomic regions.

This module provides endpoints for retrieving variants and genes within
specified genomic coordinates.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from gnomad_mcp.models import GnomadDataset
from gnomad_mcp.services import FrequencyService

from .dependencies import get_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/region", tags=["Regions"])


@router.get(
    "/{region}",
    summary="Get variants and genes in a genomic region",
    description="Query all variants and overlapping genes within specified genomic coordinates.",
    operation_id="get_region",
    responses={
        200: {
            "description": "Region data retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "chrom": "17",
                        "start": 7674232,
                        "stop": 7674252,
                        "reference_genome": "GRCh38",
                        "genes": [
                            {
                                "gene_id": "ENSG00000141510",
                                "symbol": "TP53",
                                "start": 7661779,
                                "stop": 7687538,
                            }
                        ],
                        "clinvar_variants": [
                            {
                                "variant_id": "17-7674232-C-G",
                                "clinical_significance": "Pathogenic/Likely pathogenic",
                                "gold_stars": 2,
                                "major_consequence": "missense_variant",
                                "pos": 7674232,
                                "review_status": "criteria provided, multiple submitters, no conflicts",
                            },
                            {
                                "variant_id": "17-7674241-G-A",
                                "clinical_significance": "Pathogenic",
                                "gold_stars": 3,
                                "major_consequence": "missense_variant",
                                "pos": 7674241,
                                "review_status": "reviewed by expert panel",
                            },
                        ],
                    }
                }
            },
        },
        400: {"description": "Invalid region format or coordinates"},
        500: {"description": "Internal server error"},
    },
)
async def get_region(
    region: str = Path(
        ...,
        description="Genomic region in format: chr-start-stop (e.g., 17-7674232-7674252)",
        pattern=r"^(chr)?([1-9]|1[0-9]|2[0-2]|X|Y|M|MT)-\d+-\d+$",
        openapi_examples={
            "tp53_small": {
                "summary": "TP53 small region",
                "description": "Small 20bp region in TP53 gene",
                "value": "17-7674232-7674252",
            },
            "ldlr_region": {
                "summary": "LDLR region",
                "description": "Region covering LDLR gene",
                "value": "19-11078371-11144910",
            },
            "pcsk9_region": {
                "summary": "PCSK9 region",
                "description": "Small region in PCSK9 gene",
                "value": "1-55039400-55039500",
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
        region: Genomic region in format chr-start-stop
        dataset: gnomAD dataset version (v2, v3, or v4)
        service: Injected frequency service

    Returns:
        Dictionary containing region info, variants, and genes

    Raises:
        HTTPException(400): Invalid region format or coordinates
        HTTPException(500): Internal server error
    """
    # Parse region string
    try:
        parts = region.split("-")
        if len(parts) != 3:
            raise ValueError("Region must be in format: chr-start-stop")
        
        chrom = parts[0].replace("chr", "")  # Remove chr prefix if present
        start = int(parts[1])
        stop = int(parts[2])
        
        if stop <= start:
            raise ValueError("Stop position must be greater than start position")
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        result = await service.client.get_region(chrom, start, stop, dataset)
        # Unwrap the region key if present
        if isinstance(result, dict) and "region" in result:
            return result["region"]
        return result
    except Exception as e:
        logger.error(f"Error getting region: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
