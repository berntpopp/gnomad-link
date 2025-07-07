"""Gene-related API routes."""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from gnomad_mcp.api import DataNotFoundError
from gnomad_mcp.models import Gene, GnomadDataset, ReferenceGenome
from gnomad_mcp.services import FrequencyService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gene", tags=["Genes"])

from .dependencies import get_service


@router.get(
    "/",
    response_model=Gene,
    summary="Get gene information",
    responses={
        404: {"description": "Gene not found"},
        400: {"description": "Invalid input"},
    },
)
async def get_gene(
    gene_id: Optional[str] = Query(None, description="Ensembl gene ID"),
    gene_symbol: Optional[str] = Query(None, description="Gene symbol (e.g., 'BRCA1')"),
    reference_genome: ReferenceGenome = Query(
        default=ReferenceGenome.GRCH38,
        description="Reference genome to use",
    ),
    service: FrequencyService = Depends(get_service),
) -> Gene:
    """Get gene information by ID or symbol."""
    if not gene_id and not gene_symbol:
        raise HTTPException(
            status_code=400, detail="Either gene_id or gene_symbol must be provided"
        )

    try:
        result = await service.client.get_gene(
            gene_id=gene_id, gene_symbol=gene_symbol, reference_genome=reference_genome
        )
        # Convert dict to Gene model
        return Gene(**result.get("gene", result))
    except DataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting gene: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/variants/{gene_id}",
    summary="Get variants in a gene",
    responses={
        404: {"description": "Gene not found"},
        200: {"description": "List of variants in the gene"},
    },
)
async def get_gene_variants(
    gene_id: str,
    dataset: GnomadDataset = Query(
        default=GnomadDataset.GNOMAD_R4,
        description="gnomAD dataset to query",
    ),
    service: FrequencyService = Depends(get_service),
) -> dict[str, Any]:
    """Get all variants within a gene."""
    try:
        variants = await service.client.get_gene_variants(gene_id, dataset)
        return {
            "gene_id": gene_id,
            "dataset": dataset,
            "variant_count": len(variants),
            "variants": variants,
        }
    except DataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting gene variants: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
