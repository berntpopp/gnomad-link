"""Liftover API routes for coordinate conversion between reference genomes.

This module provides endpoints for converting variant coordinates between
different reference genome builds (e.g., GRCh37 to GRCh38).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from gnomad_mcp.models import LiftoverResponse, LiftoverResult, ReferenceGenome
from gnomad_mcp.services import FrequencyService

from .dependencies import get_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/liftover", tags=["Liftover"])


@router.get(
    "/",
    response_model=LiftoverResponse,
    summary="Convert variant coordinates between reference genomes",
    description=(
        "Perform liftover of variant coordinates from one reference genome build to another. "
        "Provide source_variant_id to find the equivalent variant in the target reference genome."
    ),
    operation_id="liftover_variant",
    responses={
        200: {
            "description": "Liftover results retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "results": [
                            {
                                "source": {
                                    "variant_id": "17-7577121-G-A",
                                    "reference_genome": "GRCh37",
                                },
                                "liftover": {
                                    "variant_id": "17-7673803-G-A",
                                    "reference_genome": "GRCh38",
                                },
                                "datasets": ["gnomad_r2_1", "gnomad_r4"],
                            }
                        ],
                        "query_type": "forward",
                    }
                }
            },
        },
        500: {"description": "Internal server error"},
    },
)
async def liftover_variant(
    source_variant_id: str = Query(
        ...,
        description=(
            "Variant ID in source reference genome to liftover. "
            "Format: chromosome-position-ref-alt"
        ),
        openapi_examples={
            "tp53_grch37": {
                "summary": "TP53 variant in GRCh37",
                "description": "TP53 R273H variant in GRCh37 coordinates",
                "value": "17-7577121-G-A",
            },
            "apoe_grch37": {
                "summary": "APOE variant in GRCh37",
                "description": "APOE ε4 variant in GRCh37 coordinates",
                "value": "19-45411941-T-C",
            },
            "brca1_grch37": {
                "summary": "BRCA1 variant in GRCh37",
                "description": "BRCA1 pathogenic variant in GRCh37",
                "value": "17-41244936-G-A",
            },
        },
    ),
    reference_genome: ReferenceGenome = Query(
        ...,
        description="Source reference genome of the variant",
    ),
    service: FrequencyService = Depends(get_service),
) -> LiftoverResponse:
    """Convert variant coordinates between reference genome builds.

    This endpoint performs coordinate liftover to find the equivalent variant
    in a different reference genome build.

    Args:
        source_variant_id: Variant ID to liftover
        reference_genome: Source reference genome of the variant
        service: Injected frequency service

    Returns:
        LiftoverResponse with results

    Raises:
        HTTPException(500): Internal server error
    """
    # Log the liftover request
    logger.info(
        f"Liftover request: source_variant_id={source_variant_id}, "
        f"source_genome={reference_genome.value}"
    )

    try:
        # Perform liftover
        results = await service.client.get_liftover(
            source_variant_id=source_variant_id,
            reference_genome=reference_genome.value,
        )

        # Query type is always forward now
        query_type = "forward"

        # Convert the raw results to LiftoverResult objects
        liftover_results = []
        for item in results:
            try:
                liftover_results.append(LiftoverResult(**item))
            except Exception as e:
                logger.warning(
                    f"Failed to parse liftover result: {e}, raw item: {item}"
                )
                # Don't include invalid results
                continue

        # Log info about the results
        if not liftover_results:
            logger.info(
                f"No liftover mapping found for source_variant_id={source_variant_id} "
                f"from reference_genome={reference_genome.value}"
            )

        return LiftoverResponse(
            results=liftover_results,
            query_type=query_type,
        )

    except Exception as e:
        logger.error(f"Error performing liftover: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
