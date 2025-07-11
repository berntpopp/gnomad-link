"""Structural variant API routes for querying gnomAD SV data.

This module provides endpoints for retrieving structural variant information
including deletions, duplications, inversions, and complex rearrangements.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from gnomad_link.api import DataNotFoundError
from gnomad_link.models import StructuralVariantDataset
from gnomad_link.services import FrequencyService

from .dependencies import get_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/structural-variant", tags=["Structural Variants"])


@router.get(
    "/{variant_id}",
    summary="Get structural variant data",
    description=(
        "Retrieve comprehensive structural variant information including "
        "population frequencies and consequences."
    ),
    operation_id="get_structural_variant",
    responses={
        200: {
            "description": "Structural variant data retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "variant_id": "DUP_CHR19_06B26177",
                        "chrom": "19",
                        "pos": 10456049,
                        "end": 10583588,
                        "length": 127539,
                        "type": "DUP",
                        "reference_genome": "GRCh38",
                        "populations": [
                            {"id": "afr", "ac": 12, "an": 8128, "af": 0.001476},
                            {
                                "id": "eur_non_finnish",
                                "ac": 5,
                                "an": 11412,
                                "af": 0.000438,
                            },
                        ],
                        "consequences": [
                            {
                                "consequence": "COPY_GAIN",
                                "genes": ["ENSG00000173213", "ENSG00000271746"],
                            }
                        ],
                        "filters": ["PASS"],
                        "copy_numbers": [
                            {"copy_number": 3, "ac": 10},
                            {"copy_number": 4, "ac": 2},
                        ],
                    }
                }
            },
        },
        404: {"description": "Structural variant not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_structural_variant(
    variant_id: str = Path(
        ...,
        description="Structural variant identifier",
        openapi_examples={
            "duplication": {
                "summary": "Duplication variant",
                "description": "Example duplication in chromosome 19",
                "value": "DUP_CHR19_06B26177",
            },
            "deletion_hnf1b": {
                "summary": "HNF1B deletion",
                "description": "17q12 HNF1B deletion variant",
                "value": "GD_17Q12-HNF1B__DEL",
            },
            "deletion_y": {
                "summary": "Y chromosome deletion",
                "description": "Example deletion on Y chromosome",
                "value": "DEL_CHRY_B899DC9C",
            },
        },
    ),
    dataset: StructuralVariantDataset = Query(
        default=StructuralVariantDataset.GNOMAD_SV_R4,
        description="gnomAD structural variant dataset version",
    ),
    service: FrequencyService = Depends(get_service),
) -> dict[str, Any]:
    """Get structural variant information.

    This endpoint returns comprehensive structural variant data including:
    - Variant type (DEL, DUP, INV, INS, CPX)
    - Genomic coordinates and size
    - Population allele frequencies
    - Affected genes and functional consequences
    - Quality metrics and filters

    Args:
        variant_id: Structural variant identifier (e.g., 'DUP_1_10584')
        dataset: gnomAD SV dataset version (v2.1 or v4)
        service: Injected frequency service

    Returns:
        Dictionary containing structural variant information

    Raises:
        HTTPException(404): Structural variant not found
        HTTPException(500): Internal server error
    """
    try:
        result = await service.client.get_structural_variant(variant_id, dataset)
        # Unwrap the structural_variant key from the GraphQL response
        if isinstance(result, dict) and "structural_variant" in result:
            sv_data = result["structural_variant"]
            # Check if the variant was found
            if sv_data is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Structural variant '{variant_id}' not found in dataset '{dataset}'",
                )
            return sv_data  # type: ignore[no-any-return]
        return result  # type: ignore[no-any-return]
    except DataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting structural variant: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
