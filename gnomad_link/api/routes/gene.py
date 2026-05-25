"""Gene-related API routes for querying gnomAD gene data.

This module provides endpoints for retrieving gene information, including
constraint metrics, pLI scores, and variants within genes.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from gnomad_link.api import DataNotFoundError
from gnomad_link.models import Gene, GnomadDataset, ReferenceGenome
from gnomad_link.services import FrequencyService

from .dependencies import get_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gene", tags=["Genes"])


@router.get(
    "/",
    response_model=Gene,
    summary="Get gene information",
    description="Retrieve comprehensive gene information including constraint scores and pLI values.",
    operation_id="get_gene_details",
    responses={
        200: {
            "description": "Gene information retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "gene_id": "ENSG00000169174",
                        "gene_version": "14",
                        "symbol": "PCSK9",
                        "hgnc_id": "HGNC:20001",
                        "name": "proprotein convertase subtilisin/kexin type 9",
                        "canonical_transcript_id": "ENST00000302118",
                        "chrom": "1",
                        "start": 55039549,
                        "stop": 55064852,
                        "strand": "+",
                        "reference_genome": "GRCh38",
                        "constraint": {
                            "exp_lof": 52.4,
                            "exp_mis": 712.3,
                            "exp_syn": 234.1,
                            "obs_lof": 2,
                            "obs_mis": 651,
                            "obs_syn": 245,
                            "oe_lof": 0.038,
                            "oe_lof_lower": 0.009,
                            "oe_lof_upper": 0.114,
                            "lof_z": 5.32,
                            "pLI": 0.999,
                            "flags": [],
                        },
                    }
                }
            },
        },
        404: {"description": "Gene not found"},
        400: {"description": "Either gene_id or gene_symbol must be provided"},
    },
)
async def get_gene(
    gene_id: str | None = Query(
        None,
        description="Ensembl gene ID",
        openapi_examples={
            "brca2": {
                "summary": "BRCA2 gene ID",
                "description": "Ensembl ID for BRCA2",
                "value": "ENSG00000139618",
            },
        },
    ),
    gene_symbol: str | None = Query(
        None,
        description="Gene symbol",
        openapi_examples={
            "brca2": {
                "summary": "BRCA2 gene symbol",
                "description": "Breast cancer susceptibility gene 2",
                "value": "BRCA2",
            },
            "brca1": {
                "summary": "BRCA1 gene symbol",
                "description": "Breast cancer susceptibility gene 1",
                "value": "BRCA1",
            },
            "tp53": {
                "summary": "TP53 gene symbol",
                "description": "Tumor suppressor gene",
                "value": "TP53",
            },
            "apc": {
                "summary": "APC gene symbol",
                "description": "Adenomatous polyposis coli gene",
                "value": "APC",
            },
            "pcsk9": {
                "summary": "PCSK9 gene symbol",
                "description": "Proprotein convertase subtilisin/kexin type 9",
                "value": "PCSK9",
            },
        },
    ),
    reference_genome: ReferenceGenome = Query(
        default=ReferenceGenome.GRCH38,
        description="Reference genome build",
    ),
    service: FrequencyService = Depends(get_service),
) -> Gene:
    """Get gene information by ID or symbol.

    This endpoint returns comprehensive gene information including:
    - Basic gene metadata (name, location, transcripts)
    - Constraint metrics (observed/expected variant counts)
    - Loss-of-function intolerance scores (pLI)
    - Missense and synonymous constraint z-scores

    Either gene_id or gene_symbol must be provided.

    Args:
        gene_id: Ensembl gene ID (e.g., 'ENSG00000169174')
        gene_symbol: HGNC gene symbol (e.g., 'PCSK9')
        reference_genome: Reference genome build (GRCh37 or GRCh38)
        service: Injected frequency service

    Returns:
        Gene object with complete gene information

    Raises:
        HTTPException(404): Gene not found
        HTTPException(400): Neither gene_id nor gene_symbol provided
        HTTPException(500): Internal server error
    """
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
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error getting gene: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get(
    "/variants/{gene_id}",
    summary="Get variants in a gene",
    description="Retrieve all variants located within a gene's boundaries.",
    operation_id="get_gene_variants",
    responses={
        200: {
            "description": "List of variants in the gene",
            "content": {
                "application/json": {
                    "example": {
                        "gene_id": "ENSG00000169174",
                        "dataset": "gnomad_r4",
                        "variant_count": 847,
                        "variants": [
                            {
                                "variant_id": "1-55039568-G-A",
                                "rsid": "rs121908004",
                                "consequence": "missense_variant",
                                "hgvsp": "p.Ser127Arg",
                                "af": 0.000012,
                                "ac": 2,
                                "an": 152334,
                            }
                        ],
                    }
                }
            },
        },
        404: {"description": "Gene not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_gene_variants(
    gene_id: str,
    dataset: GnomadDataset = Query(
        default=GnomadDataset.GNOMAD_R4,
        description="gnomAD dataset version to query",
    ),
    service: FrequencyService = Depends(get_service),
) -> dict[str, Any]:
    """Get all variants within a gene.

    This endpoint returns all variants that fall within the genomic boundaries
    of the specified gene. Each variant includes basic information such as:
    - Variant ID and rsID
    - Functional consequence
    - Protein change (if applicable)
    - Allele frequency data

    Args:
        gene_id: Ensembl gene ID (e.g., 'ENSG00000169174')
        dataset: gnomAD dataset version (v2, v3, or v4)
        service: Injected frequency service

    Returns:
        Dictionary containing gene_id, dataset, variant count, and list of variants

    Raises:
        HTTPException(404): Gene not found
        HTTPException(500): Internal server error
    """
    try:
        variants = await service.client.get_gene_variants(gene_id, dataset)
        return {
            "gene_id": gene_id,
            "dataset": dataset,
            "variant_count": len(variants),
            "variants": variants,
        }
    except DataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error getting gene variants: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
