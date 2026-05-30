"""Live expression-population check for get_gene_summary. Gated by `integration`."""

from __future__ import annotations

import pytest

from gnomad_link.api.client import UnifiedGnomadClient
from gnomad_link.services.gene_summary_service import GeneSummaryService

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_pcsk9_expression_populated_from_grch37_not_grch38() -> None:
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
    # GRCh38 pext is empty upstream; the service backfills from GRCh37.
    assert expr.get("source_build") == "GRCh37"
    assert expr.get("mean_pext") is not None
    assert len(expr.get("top_tissues") or []) >= 1


@pytest.mark.asyncio
async def test_grch38_gene_pext_is_empty_directly() -> None:
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
    assert regions == [], "GRCh38 pext expected empty; expression must come from GRCh37"
