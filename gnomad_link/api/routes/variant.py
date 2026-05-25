"""Variant-related API routes for querying gnomAD variant data.

This module provides endpoints for retrieving variant frequency data and detailed
variant information from the gnomAD database.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from gnomad_link.api import DataNotFoundError, GnomadApiError
from gnomad_link.models import GnomadDataset, VariantFrequencyResponse
from gnomad_link.services import FrequencyService

from .dependencies import get_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/variant", tags=["Variants"])


@router.get(
    "/{variant_id}",
    response_model=VariantFrequencyResponse,
    summary="Get variant frequency data",
    description=(
        "Retrieve allele frequency data for a specific variant across different "
        "populations and subpopulations."
    ),
    operation_id="get_variant_frequency_data",
    responses={
        200: {
            "description": "Variant frequency data retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "variant_id": "1-55051215-G-GA",
                        "rsid": "rs11591147",
                        "dataset": "gnomad_r4",
                        "genome": {
                            "ac": 2,
                            "an": 152302,
                            "af": 0.0000131,
                            "populations": [{"id": "afr", "ac": 1, "an": 41562, "af": 0.0000241}],
                        },
                    }
                }
            },
        },
        404: {"description": "Variant not found in the specified dataset"},
        400: {"description": "Invalid variant ID format"},
        502: {"description": "Upstream gnomAD API error"},
        500: {"description": "Internal server error"},
    },
)
async def get_variant(
    variant_id: str = Path(
        ...,
        description="Variant identifier in format: chromosome-position-ref-alt",
        pattern=r"^[^'\"]+$",
        openapi_examples={
            "brca2_deletion": {
                "summary": "BRCA2 pathogenic deletion",
                "description": "Pathogenic frameshift variant in BRCA2 causing hereditary breast/ovarian cancer",
                "value": "13-32394863-CTG-C",
            },
            "brca1_missense": {
                "summary": "BRCA1 pathogenic missense",
                "description": "Pathogenic missense variant in BRCA1",
                "value": "17-7674232-C-T",
            },
            "tp53_missense": {
                "summary": "TP53 missense variant",
                "description": "TP53 R175H hotspot mutation in Li-Fraumeni syndrome",
                "value": "17-7674221-G-A",
            },
            "pcsk9_frameshift": {
                "summary": "PCSK9 protective variant",
                "description": "Loss-of-function variant associated with low LDL cholesterol",
                "value": "1-55051215-G-GA",
            },
        },
    ),
    dataset: GnomadDataset = Query(
        default=GnomadDataset.GNOMAD_R4,
        description="gnomAD dataset version to query",
    ),
    service: FrequencyService = Depends(get_service),
) -> VariantFrequencyResponse:
    """Retrieve allele frequency data for a specific variant.

    This endpoint returns population-level allele counts, allele numbers, and
    allele frequencies for the specified variant. The data includes breakdowns
    by genetic ancestry groups and subpopulations.

    Args:
        variant_id: Variant identifier in CHROM-POS-REF-ALT format
        dataset: gnomAD dataset version (v2, v3, or v4)
        service: Injected frequency service

    Returns:
        VariantFrequencyResponse with population frequency data

    Raises:
        HTTPException(404): Variant not found in the dataset
        HTTPException(400): Invalid variant ID format
        HTTPException(502): gnomAD API communication error
        HTTPException(500): Internal server error
    """
    try:
        return await service.get_variant_frequencies(variant_id, dataset)
    except DataNotFoundError as e:
        logger.warning(f"Variant not found: {e}")
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        logger.warning(f"Invalid input: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except GnomadApiError as e:
        logger.error(f"API error: {e}")
        raise HTTPException(status_code=502, detail="Error communicating with gnomAD API") from e
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal server error occurred") from e


@router.get(
    "/details/{variant_id}",
    summary="Get detailed variant information",
    description=(
        "Retrieve comprehensive variant details including annotations, "
        "consequence predictions, and quality metrics."
    ),
    operation_id="get_variant_details",
    responses={
        200: {
            "description": "Detailed variant information retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "variant_id": "1-55051215-G-GA",
                        "reference_genome": "GRCh38",
                        "pos": 55051215,
                        "ref": "G",
                        "alt": "GA",
                        "rsids": ["rs11591147"],
                        "transcript_consequences": [
                            {
                                "gene_symbol": "PCSK9",
                                "transcript_id": "ENST00000302118",
                                "consequence_terms": ["frameshift_variant"],
                                "lof": "HC",
                                "polyphen_prediction": "probably_damaging",
                            }
                        ],
                        "quality_metrics": {
                            "allele_balance": {"alt": 0.45},
                            "genotype_depth": {"all_het": 35},
                            "genotype_quality": {"all_het": 99},
                        },
                    }
                }
            },
        },
        404: {"description": "Variant not found in the specified dataset"},
        400: {"description": "Invalid variant ID format"},
        500: {"description": "Internal server error"},
    },
)
async def get_variant_details(
    variant_id: str = Path(
        ...,
        description="Variant identifier in format: chromosome-position-ref-alt",
        openapi_examples={
            "brca2_deletion": {
                "summary": "BRCA2 pathogenic deletion",
                "description": "Pathogenic frameshift variant in BRCA2 with detailed clinical annotations",
                "value": "13-32394863-CTG-C",
            },
            "brca1_missense": {
                "summary": "BRCA1 pathogenic missense",
                "description": "BRCA1 pathogenic variant with detailed annotations",
                "value": "17-7674232-C-T",
            },
            "tp53_missense": {
                "summary": "TP53 hotspot mutation",
                "description": "TP53 R175H mutation with cancer predisposition annotations",
                "value": "17-7674221-G-A",
            },
            "apc_nonsense": {
                "summary": "APC truncating variant",
                "description": "APC nonsense variant causing familial adenomatous polyposis",
                "value": "5-112839942-C-T",
            },
        },
    ),
    dataset: GnomadDataset = Query(
        default=GnomadDataset.GNOMAD_R4,
        description="gnomAD dataset version to query",
    ),
    service: FrequencyService = Depends(get_service),
) -> dict[str, Any]:
    """Get complete variant details including annotations.

    This endpoint returns comprehensive information about a variant including:
    - Basic variant information (position, reference, alternate alleles)
    - Transcript consequences and impact predictions
    - Quality control metrics
    - In silico predictors (PolyPhen, SIFT, etc.)
    - Clinical significance annotations
    - Population frequency data

    Args:
        variant_id: Variant identifier in CHROM-POS-REF-ALT format
        dataset: gnomAD dataset version (v2, v3, or v4)
        service: Injected frequency service

    Returns:
        Dictionary containing all available variant annotations

    Raises:
        HTTPException(404): Variant not found in the dataset
        HTTPException(500): Internal server error
    """
    try:
        result = await service.client.get_variant(variant_id, dataset)
        return result
    except DataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error getting variant details: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
