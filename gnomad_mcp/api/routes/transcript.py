"""Transcript-related API routes for querying gnomAD transcript data.

This module provides endpoints for retrieving transcript information including
exon structure, expression data, and coverage statistics.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from gnomad_mcp.api import DataNotFoundError
from gnomad_mcp.models import ReferenceGenome
from gnomad_mcp.services import FrequencyService

from .dependencies import get_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transcript", tags=["Transcripts"])


@router.get(
    "/{transcript_id}",
    summary="Get transcript information",
    description="Retrieve comprehensive transcript information including exon structure and GTEx expression data.",
    operation_id="get_transcript_details",
    responses={
        200: {
            "description": "Transcript information retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "transcript_id": "ENST00000302118",
                        "transcript_version": "5",
                        "gene_id": "ENSG00000169174",
                        "gene_symbol": "PCSK9",
                        "chrom": "1",
                        "start": 55039549,
                        "stop": 55064852,
                        "strand": "+",
                        "exons": [
                            {
                                "feature_type": "CDS",
                                "start": 55039568,
                                "stop": 55039804,
                                "xstart": 55039549,
                                "xstop": 55039804,
                            }
                        ],
                        "gtex_tissue_expression": {
                            "adipose_subcutaneous": {"mean": 15.7, "median": 14.2},
                            "adipose_visceral_omentum": {"mean": 18.3, "median": 17.1},
                            "liver": {"mean": 45.2, "median": 43.8},
                        },
                    }
                }
            },
        },
        404: {"description": "Transcript not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_transcript(
    transcript_id: str = Path(
        ...,
        description="Ensembl transcript ID",
        openapi_examples={
            "brca2": {
                "summary": "BRCA2 canonical transcript",
                "description": "Main transcript for BRCA2 gene",
                "value": "ENST00000380152",
            },
            "brca1": {
                "summary": "BRCA1 canonical transcript",
                "description": "Main transcript for BRCA1 gene",
                "value": "ENST00000357654",
            },
            "tp53": {
                "summary": "TP53 canonical transcript",
                "description": "Main transcript for TP53 gene",
                "value": "ENST00000269305",
            },
            "pcsk9": {
                "summary": "PCSK9 canonical transcript",
                "description": "Canonical transcript for PCSK9 gene",
                "value": "ENST00000302118",
            },
        },
    ),
    reference_genome: ReferenceGenome = Query(
        default=ReferenceGenome.GRCH38,
        description="Reference genome build",
    ),
    service: FrequencyService = Depends(get_service),
) -> dict[str, Any]:
    """Get transcript information including exons and expression data.

    This endpoint returns comprehensive transcript information including:
    - Basic transcript metadata (gene, location, strand)
    - Exon structure with coding sequence boundaries
    - GTEx tissue expression levels (if available)
    - Canonical transcript status

    Args:
        transcript_id: Ensembl transcript ID (e.g., 'ENST00000302118')
        reference_genome: Reference genome build (GRCh37 or GRCh38)
        service: Injected frequency service

    Returns:
        Dictionary containing transcript information and annotations

    Raises:
        HTTPException(404): Transcript not found
        HTTPException(500): Internal server error
    """
    # Basic validation of transcript ID format
    if not transcript_id.startswith("ENST") or len(transcript_id) < 15:
        raise HTTPException(
            status_code=404,
            detail=f"Invalid transcript ID format: '{transcript_id}'. Expected format: ENST followed by 11 digits (e.g., ENST00000357654)"
        )
    
    try:
        result = await service.client.get_transcript(transcript_id, reference_genome)
        # Unwrap the transcript key from the GraphQL response
        if isinstance(result, dict) and "transcript" in result:
            transcript_data = result["transcript"]
            # Check if the transcript was found
            if transcript_data is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Transcript '{transcript_id}' not found for reference genome '{reference_genome}'"
                )
            return transcript_data
        return result
    except DataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except HTTPException:
        raise
    except TimeoutError:
        # Timeouts often indicate invalid transcript IDs that the API can't process
        raise HTTPException(
            status_code=404,
            detail=f"Transcript '{transcript_id}' not found or request timed out"
        ) from None
    except Exception as e:
        logger.error(f"Error getting transcript: {e}")
        # Check if it's a timeout wrapped in another exception
        if "timeout" in str(e).lower():
            raise HTTPException(
                status_code=404,
                detail=f"Transcript '{transcript_id}' not found or request timed out"
            ) from e
        raise HTTPException(status_code=500, detail="Internal server error") from e
