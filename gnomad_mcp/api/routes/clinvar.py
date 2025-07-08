"""ClinVar-related API routes for querying clinical variant data.

This module provides endpoints for retrieving ClinVar clinical significance
annotations for genetic variants.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query

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
    description="Retrieve ClinVar clinical significance and submission data for a genetic variant.",
    operation_id="get_clinvar_variant",
    responses={
        200: {
            "description": "ClinVar variant data retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "clinvar_variation_id": "30856",
                        "variant_id": "1-55051215-G-GA",
                        "reference_genome": "GRCh38",
                        "chrom": "1",
                        "pos": 55051215,
                        "ref": "G",
                        "alt": "GA",
                        "clinical_significance": "Benign",
                        "gold_stars": 2,
                        "review_status": "criteria provided, multiple submitters, no conflicts",
                        "last_evaluated": "2023-08-15",
                        "submissions": [
                            {
                                "clinical_significance": "Benign",
                                "last_evaluated": "2023-08-15",
                                "review_status": "criteria provided, single submitter",
                                "conditions": [
                                    {
                                        "name": "Familial hypercholesterolemia",
                                        "medgen_id": "C0020445",
                                    }
                                ],
                                "submitter_name": "GeneDx",
                            }
                        ],
                    }
                }
            },
        },
        404: {"description": "Variant not found in ClinVar"},
        500: {"description": "Internal server error"},
    },
)
async def get_clinvar_variant(
    variant_id: str = Path(
        ...,
        description="Variant identifier in format: chromosome-position-ref-alt",
        openapi_examples={
            "pathogenic_brca2": {
                "summary": "BRCA2 pathogenic variant",
                "description": "ClinVar pathogenic variant causing hereditary breast/ovarian cancer",
                "value": "13-32394863-CTG-C",
            },
            "pathogenic_tp53": {
                "summary": "TP53 pathogenic variant",
                "description": "TP53 R175H hotspot mutation in Li-Fraumeni syndrome",
                "value": "17-7674221-G-A",
            },
            "pathogenic_brca1": {
                "summary": "BRCA1 pathogenic variant",
                "description": "BRCA1 pathogenic variant",
                "value": "17-7674232-C-T",
            },
            "benign_variant": {
                "summary": "Benign variant",
                "description": "Common benign variant with high population frequency",
                "value": "1-55051215-G-GA",
            },
        },
    ),
    reference_genome: ReferenceGenome = Query(
        default=ReferenceGenome.GRCH38,
        description="Reference genome build",
    ),
    service: FrequencyService = Depends(get_service),
) -> ClinVarVariant:
    """Get ClinVar clinical significance data for a variant.

    This endpoint returns ClinVar annotations including:
    - Clinical significance (Pathogenic, Benign, VUS, etc.)
    - Review status and gold star rating
    - Submission details from clinical laboratories
    - Associated conditions and phenotypes
    - Last evaluation date

    Args:
        variant_id: Variant identifier in CHROM-POS-REF-ALT format
        reference_genome: Reference genome build (GRCh37 or GRCh38)
        service: Injected frequency service

    Returns:
        ClinVarVariant object with clinical annotations

    Raises:
        HTTPException(404): Variant not found in ClinVar
        HTTPException(500): Internal server error
    """
    try:
        result = await service.client.get_clinvar_variant(variant_id, reference_genome)
        return ClinVarVariant(**result.get("clinvar_variant", result))
    except DataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error getting ClinVar variant: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get(
    "/meta",
    summary="Get ClinVar metadata",
    description="Retrieve metadata about the ClinVar database including release date.",
    operation_id="get_clinvar_meta",
    responses={
        200: {
            "description": "ClinVar metadata retrieved successfully",
            "content": {
                "application/json": {"example": {"clinvar_release_date": "2025-04-29"}}
            },
        },
        500: {"description": "Internal server error"},
    },
)
async def get_clinvar_meta(
    service: FrequencyService = Depends(get_service),
) -> dict[str, Any]:
    """Get ClinVar metadata including release date.

    This endpoint returns metadata about the ClinVar database such as:
    - Release date of the ClinVar data integrated into gnomAD

    Args:
        service: Injected frequency service

    Returns:
        Dictionary containing ClinVar metadata

    Raises:
        HTTPException(500): Internal server error
    """
    try:
        result = await service.client.get_meta()
        # Extract only ClinVar-specific metadata
        meta_data = result.get("meta", {})
        return {"clinvar_release_date": meta_data.get("clinvar_release_date")}
    except Exception as e:
        logger.error(f"Error getting ClinVar metadata: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
