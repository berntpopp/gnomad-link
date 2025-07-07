"""Mitochondrial variant API routes for querying gnomAD mitochondrial data.

This module provides endpoints for retrieving mitochondrial variant information
including heteroplasmy levels and haplogroup distributions.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from gnomad_mcp.api import DataNotFoundError
from gnomad_mcp.models import GnomadDataset
from gnomad_mcp.services import FrequencyService

from .dependencies import get_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mitochondrial-variant", tags=["Mitochondrial Variants"])


@router.get(
    "/{variant_id}",
    summary="Get mitochondrial variant data",
    description="Retrieve mitochondrial variant information including heteroplasmy levels and population frequencies.",
    operation_id="get_mitochondrial_variant",
    responses={
        200: {
            "description": "Mitochondrial variant data retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "variant_id": "M-8602-T-C",
                        "rsid": "rs28358569",
                        "pos": 8602,
                        "ref": "T",
                        "alt": "C",
                        "an": 56434,
                        "ac_hom": 15,
                        "ac_het": 42,
                        "af_hom": 0.000266,
                        "af_het": 0.000744,
                        "max_heteroplasmy": 0.95,
                        "haplogroups": [
                            {"id": "H", "an": 23456, "ac_hom": 8, "ac_het": 12},
                            {"id": "U", "an": 12345, "ac_hom": 3, "ac_het": 10},
                        ],
                        "populations": [
                            {"id": "eur", "an": 25432, "ac_hom": 10, "ac_het": 25}
                        ],
                        "age_distribution": {
                            "het": {
                                "bin_edges": [20, 30, 40, 50, 60, 70, 80],
                                "bin_freq": [2, 5, 8, 12, 10, 5, 0],
                            }
                        },
                    }
                }
            },
        },
        404: {"description": "Mitochondrial variant not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_mitochondrial_variant(
    variant_id: str = Path(
        ...,
        description="Mitochondrial variant identifier in format: M-position-ref-alt",
        openapi_examples={
            "common": {
                "summary": "Common mitochondrial variant",
                "description": "Example of a common mitochondrial variant",
                "value": "M-8602-T-C",
            },
            "pathogenic": {
                "summary": "Pathogenic mitochondrial variant",
                "description": "MELAS syndrome variant",
                "value": "M-3243-A-G",
            },
            "deafness": {
                "summary": "Deafness-associated variant",
                "description": "Aminoglycoside-induced deafness variant",
                "value": "M-1555-A-G",
            },
        },
    ),
    dataset: GnomadDataset = Query(
        default=GnomadDataset.GNOMAD_R4,
        description="gnomAD dataset version to query",
    ),
    service: FrequencyService = Depends(get_service),
) -> dict[str, Any]:
    """Get mitochondrial variant information with heteroplasmy data.

    This endpoint returns comprehensive mitochondrial variant data including:
    - Homoplasmic and heteroplasmic allele counts and frequencies
    - Maximum observed heteroplasmy level
    - Haplogroup-specific frequencies
    - Age distribution of carriers
    - Population-specific frequencies

    Args:
        variant_id: Mitochondrial variant ID in M-POS-REF-ALT format
        dataset: gnomAD dataset version (v3.1 or v4)
        service: Injected frequency service

    Returns:
        Dictionary containing mitochondrial variant information

    Raises:
        HTTPException(404): Mitochondrial variant not found
        HTTPException(500): Internal server error
    """
    try:
        result = await service.client.get_mitochondrial_variant(variant_id, dataset)
        return result
    except DataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error getting mitochondrial variant: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
