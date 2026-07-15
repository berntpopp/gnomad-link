"""get_gene_details leads with a plain-English constraint headline."""

from __future__ import annotations

import pytest

from gnomad_link.models.gene_models import Gene, GeneConstraint


class _StubGeneService:
    def __init__(self, gene: Gene) -> None:
        self._gene = gene

    async def get_gene(
        self,
        *,
        gene_id: str | None = None,
        gene_symbol: str | None = None,
        reference_genome: str = "GRCh38",
    ) -> Gene:
        return self._gene


def _pcsk9() -> Gene:
    return Gene(
        gene_id="ENSG00000169174",
        symbol="PCSK9",
        chrom="1",
        start=55039447,
        stop=55064852,
        gnomad_constraint=GeneConstraint(pli=0.0042, oe_lof=0.83),
    )


@pytest.mark.asyncio
async def test_get_gene_details_leads_with_constraint_headline() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=lambda: _StubGeneService(_pcsk9()))
    result = await mcp.call_tool(
        "get_gene_details",
        {"gene": "PCSK9", "reference_genome": "GRCh38"},
    )
    payload = result.structured_content or {}

    headline = payload["headline"]
    assert headline == (
        "PCSK9 (ENSG00000169174): pLI 0.004, LoF o/e 0.83; 1:55039447-55064852 (GRCh38)."
    )
