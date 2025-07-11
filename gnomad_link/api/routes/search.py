"""Search API routes for querying gnomAD data.

This module provides endpoints for searching genes, variants, and other
genomic features across the gnomAD database.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from gnomad_link.models import GeneSearchResult, GnomadDataset, ReferenceGenome
from gnomad_link.services import FrequencyService

from .dependencies import get_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["Search"])


@router.get(
    "/gene",
    response_model=list[GeneSearchResult],
    summary="Search for genes",
    description="Search for genes by symbol, name, or Ensembl ID with fuzzy matching support.",
    operation_id="search_genes",
    responses={
        200: {
            "description": "Gene search results",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "gene_id": "ENSG00000169174",
                            "gene_version": "14",
                            "symbol": "PCSK9",
                            "hgnc_id": "HGNC:20001",
                            "name": "proprotein convertase subtilisin/kexin type 9",
                            "canonical_transcript_id": "ENST00000302118",
                            "chrom": "1",
                            "start": 55039549,
                            "stop": 55064852,
                            "reference_genome": "GRCh38",
                        },
                        {
                            "gene_id": "ENSG00000284415",
                            "gene_version": "1",
                            "symbol": "PCSK9-AS1",
                            "name": "PCSK9 antisense RNA 1",
                            "chrom": "1",
                            "start": 55039447,
                            "stop": 55040267,
                            "reference_genome": "GRCh38",
                        },
                    ]
                }
            },
        },
        400: {"description": "Query too short (minimum 2 characters)"},
        500: {"description": "Internal server error"},
    },
)
async def search_genes(
    query: str = Query(
        ...,
        description="Search query (gene symbol, name, or Ensembl ID)",
        min_length=2,
        openapi_examples={
            "brca_search": {
                "summary": "BRCA gene search",
                "description": "Search for BRCA genes",
                "value": "BRCA",
            },
            "tp53": {
                "summary": "TP53 search",
                "description": "Search for tumor protein p53",
                "value": "TP53",
            },
            "apc": {
                "summary": "APC search",
                "description": "Search for adenomatous polyposis coli gene",
                "value": "APC",
            },
            "pcsk9": {
                "summary": "PCSK9 search",
                "description": "Search for PCSK9 gene",
                "value": "PCSK9",
            },
        },
    ),
    reference_genome: ReferenceGenome = Query(
        default=ReferenceGenome.GRCH38,
        description="Reference genome build",
    ),
    service: FrequencyService = Depends(get_service),
) -> list[GeneSearchResult]:
    """Search for genes by symbol or Ensembl ID.

    This endpoint performs fuzzy searching across:
    - Gene symbols (e.g., 'PCSK9')
    - Gene names (e.g., 'proprotein convertase')
    - Ensembl gene IDs (e.g., 'ENSG00000169174')

    The search is case-insensitive and supports partial matches.

    Args:
        query: Search string (minimum 2 characters)
        reference_genome: Reference genome build (GRCh37 or GRCh38)
        service: Injected frequency service

    Returns:
        List of matching genes with basic metadata

    Raises:
        HTTPException(400): Query too short
        HTTPException(500): Internal server error
    """
    try:
        results = await service.client.search_genes(query, reference_genome)
        return [GeneSearchResult(**r) for r in results]
    except Exception as e:
        logger.error(f"Error searching genes: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get(
    "/variant",
    summary="Search for variants",
    description="Search for variants by ID, rsID, or genomic position.",
    operation_id="search_variants",
    responses={
        200: {
            "description": "Variant search results",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "variant_id": "1-55051215-G-GA",
                            "rsid": "rs11591147",
                            "gene_symbol": "PCSK9",
                            "consequence": "frameshift_variant",
                            "hgvsp": "p.Leu22ValfsTer16",
                            "af": 0.0131,
                            "dataset": "gnomad_r4",
                        },
                        {
                            "variant_id": "1-55051215-G-A",
                            "rsid": "rs505151",
                            "gene_symbol": "PCSK9",
                            "consequence": "missense_variant",
                            "hgvsp": "p.Glu22Lys",
                            "af": 0.0024,
                            "dataset": "gnomad_r4",
                        },
                    ]
                }
            },
        },
        400: {"description": "Query too short (minimum 3 characters)"},
        500: {"description": "Internal server error"},
    },
)
async def search_variants(
    query: str = Query(
        ...,
        description="Variant ID, rsID, or position",
        min_length=3,
        openapi_examples={
            "brca2_variant": {
                "summary": "BRCA2 variant search",
                "description": "Search for BRCA2 pathogenic deletion",
                "value": "13-32394863-CTG-C",
            },
            "tp53_variant": {
                "summary": "TP53 variant search",
                "description": "Search for TP53 R175H mutation",
                "value": "17-7674221-G-A",
            },
            "rsid": {
                "summary": "rsID search",
                "description": "Search by dbSNP rsID",
                "value": "rs80357906",
            },
            "position": {
                "summary": "Position search",
                "description": "Search by BRCA2 genomic position",
                "value": "13:32394863",
            },
        },
    ),
    dataset: GnomadDataset = Query(
        default=GnomadDataset.GNOMAD_R4,
        description="gnomAD dataset version to query",
    ),
    service: FrequencyService = Depends(get_service),
) -> list[dict[str, Any]]:
    """Search for variants by ID or rsID.

    This endpoint searches for variants using:
    - Full variant ID (e.g., '1-55051215-G-GA')
    - rsID (e.g., 'rs11591147')
    - Genomic position (e.g., '1:55051215')

    The search returns basic variant information including consequences
    and allele frequencies.

    Args:
        query: Search string (minimum 3 characters)
        dataset: gnomAD dataset version (v2, v3, or v4)
        service: Injected frequency service

    Returns:
        List of matching variants with basic annotations

    Raises:
        HTTPException(400): Query too short
        HTTPException(500): Internal server error
    """
    try:
        results = await service.client.search_variants(query, dataset)
        return results
    except Exception as e:
        logger.error(f"Error searching variants: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
