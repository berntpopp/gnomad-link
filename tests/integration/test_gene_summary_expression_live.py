"""Live expression-population check for get_gene_summary. Gated by `integration`.

Verified against gnomAD r4 (2026-05): GRCh38 `gene.pext` is populated, and GTEx
tissue expression is available via `gene.transcripts[].gtex_tissue_expression`
(the standalone `transcript(id).gtex_tissue_expression` field is unavailable on
GRCh38 and errors on GRCh37). Expression therefore sources from GRCh38.
"""

from __future__ import annotations

import pytest

from gnomad_link.api.client import UnifiedGnomadClient
from gnomad_link.services.gene_summary_service import GeneSummaryService

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_pcsk9_expression_populated_from_grch38() -> None:
    client = UnifiedGnomadClient()
    try:
        svc = GeneSummaryService(client=client)
        result = await svc.get_gene_summary(
            gene_id="ENSG00000169174",
            gene_symbol=None,
            dataset="gnomad_r4",
            include_expression=True,
        )
    finally:
        await client.close()

    expr = result["expression"]
    assert expr.get("unavailable") is not True
    assert expr.get("source_build") == "GRCh38"
    assert expr.get("mean_pext") is not None
    assert len(expr.get("top_tissues") or []) >= 1


@pytest.mark.asyncio
async def test_grch38_gene_pext_is_populated_directly() -> None:
    client = UnifiedGnomadClient()
    try:
        raw = await client.get_gene_summary(
            gene_id="ENSG00000169174",
            gene_symbol=None,
            reference_genome="GRCh38",
            dataset="gnomad_r4",
        )
    finally:
        await client.close()

    gene = raw["gene"]
    regions = (gene.get("pext") or {}).get("regions") or []
    assert regions, "GRCh38 pext expected populated for PCSK9"


@pytest.mark.asyncio
async def test_grch38_canonical_transcript_gtex_via_gene() -> None:
    client = UnifiedGnomadClient()
    try:
        raw = await client.get_gene_gtex(
            gene_id="ENSG00000169174",
            reference_genome="GRCh38",
        )
    finally:
        await client.close()

    gene = raw["gene"]
    canonical = gene.get("canonical_transcript_id")
    transcripts = gene.get("transcripts") or []
    matched = [t for t in transcripts if t.get("transcript_id") == canonical]
    assert matched, "canonical transcript should appear in gene.transcripts"
    assert matched[0].get("gtex_tissue_expression"), "canonical transcript should carry GTEx"
