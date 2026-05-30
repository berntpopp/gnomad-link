"""Live gene-level carrier-frequency check. Gated by `integration`.

Ground truth: the gnomad-carrier-frequency calculator (CLI/web) for CFTR on
gnomAD r4 with default settings -> global carrier ~5.68% (1 in 18), NFE ~6.31%,
Ashkenazi Jewish ~11.06%. Numbers may drift slightly with gnomAD releases.
"""

from __future__ import annotations

import pytest

from gnomad_link.api.client import UnifiedGnomadClient
from gnomad_link.services.gene_carrier_filters import FilterConfig
from gnomad_link.services.gene_carrier_service import GeneCarrierService

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_cftr_gene_carrier_matches_reference() -> None:
    client = UnifiedGnomadClient()
    try:
        svc = GeneCarrierService(client=client)
        result = await svc.get_gene_carrier_frequency(
            gene_symbol="CFTR",
            dataset="gnomad_r4",
            filter_config=FilterConfig(),
            method="hom_exclusion",
        )
    finally:
        await client.close()

    assert result["qualifying_count"] > 300
    assert result["global"]["carrier_frequency"] == pytest.approx(0.0568, abs=0.006)
    assert result["populations"]["nfe"]["carrier_frequency"] == pytest.approx(0.0631, abs=0.006)
    assert result["populations"]["asj"]["carrier_frequency"] == pytest.approx(0.1106, abs=0.01)


@pytest.mark.asyncio
async def test_cftr_method_simplified_overestimates_hwe() -> None:
    client = UnifiedGnomadClient()
    try:
        svc = GeneCarrierService(client=client)
        hwe = await svc.get_gene_carrier_frequency(
            gene_symbol="CFTR", dataset="gnomad_r4", method="hwe"
        )
        simplified = await svc.get_gene_carrier_frequency(
            gene_symbol="CFTR", dataset="gnomad_r4", method="simplified"
        )
    finally:
        await client.close()

    # 2*sumAF >= 2pq for the same q.
    assert simplified["global"]["carrier_frequency"] >= hwe["global"]["carrier_frequency"]
