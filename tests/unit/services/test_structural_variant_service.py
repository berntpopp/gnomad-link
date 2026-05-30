"""Unit tests for StructuralVariantService gene/region SV search.

Offline: the gnomAD client is an AsyncMock; the service must shape the
nested GraphQL envelope ({"gene": {"structural_variants": [...]}} or
{"region": {"structural_variants": [...]}}) into a flat list of dicts.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from gnomad_link.services.structural_variant_service import StructuralVariantService

_SV_ROWS = [
    {
        "variant_id": "DEL_19_1",
        "type": "DEL",
        "chrom": "19",
        "pos": 11_089_000,
        "end": 11_133_820,
        "length": 44_820,
        "af": 0.0001,
        "ac": 3,
        "an": 30000,
        "major_consequence": "lof",
    },
    {
        "variant_id": "DUP_19_2",
        "type": "DUP",
        "chrom": "19",
        "pos": 11_100_000,
        "end": 11_200_000,
        "length": 100_000,
        "af": 0.002,
        "ac": 60,
        "an": 30000,
        "major_consequence": "copy_gain",
    },
]


@pytest.fixture
def service_with_client():
    client = AsyncMock()
    return StructuralVariantService(client=client), client


@pytest.mark.asyncio
async def test_search_by_gene_symbol_returns_flat_list(service_with_client) -> None:
    service, client = service_with_client
    client.search_structural_variants_by_gene.return_value = list(_SV_ROWS)

    rows = await service.search_structural_variants(
        gene_symbol="SMARCA4", sv_dataset="gnomad_sv_r4"
    )

    client.search_structural_variants_by_gene.assert_awaited_once_with(
        gene_id=None,
        gene_symbol="SMARCA4",
        reference_genome="GRCh38",
        sv_dataset="gnomad_sv_r4",
    )
    assert [r["variant_id"] for r in rows] == ["DEL_19_1", "DUP_19_2"]


@pytest.mark.asyncio
async def test_search_by_gene_id_uses_gene_id(service_with_client) -> None:
    service, client = service_with_client
    client.search_structural_variants_by_gene.return_value = list(_SV_ROWS)

    await service.search_structural_variants(gene_id="ENSG00000127616", sv_dataset="gnomad_sv_r4")

    client.search_structural_variants_by_gene.assert_awaited_once_with(
        gene_id="ENSG00000127616",
        gene_symbol=None,
        reference_genome="GRCh38",
        sv_dataset="gnomad_sv_r4",
    )


@pytest.mark.asyncio
async def test_search_by_region_parses_and_delegates(service_with_client) -> None:
    service, client = service_with_client
    client.search_structural_variants_by_region.return_value = list(_SV_ROWS)

    rows = await service.search_structural_variants(
        region="19-11089000-11200000", sv_dataset="gnomad_sv_r4"
    )

    client.search_structural_variants_by_region.assert_awaited_once_with(
        chrom="19",
        start=11_089_000,
        stop=11_200_000,
        reference_genome="GRCh38",
        sv_dataset="gnomad_sv_r4",
    )
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_r2_1_maps_to_grch37(service_with_client) -> None:
    service, client = service_with_client
    client.search_structural_variants_by_gene.return_value = []

    await service.search_structural_variants(gene_symbol="SMARCA4", sv_dataset="gnomad_sv_r2_1")

    client.search_structural_variants_by_gene.assert_awaited_once_with(
        gene_id=None,
        gene_symbol="SMARCA4",
        reference_genome="GRCh37",
        sv_dataset="gnomad_sv_r2_1",
    )


@pytest.mark.asyncio
async def test_requires_exactly_one_entry_argument(service_with_client) -> None:
    service, _ = service_with_client

    with pytest.raises(ValueError, match="exactly one"):
        await service.search_structural_variants(sv_dataset="gnomad_sv_r4")

    with pytest.raises(ValueError, match="exactly one"):
        await service.search_structural_variants(
            gene_symbol="SMARCA4", region="19-1-2", sv_dataset="gnomad_sv_r4"
        )


@pytest.mark.asyncio
async def test_invalid_sv_dataset_rejected(service_with_client) -> None:
    service, _ = service_with_client

    with pytest.raises(ValueError, match="sv_dataset"):
        await service.search_structural_variants(gene_symbol="SMARCA4", sv_dataset="gnomad_r4")


@pytest.mark.asyncio
async def test_malformed_region_rejected(service_with_client) -> None:
    service, _ = service_with_client

    with pytest.raises(ValueError, match="region"):
        await service.search_structural_variants(region="not-a-region", sv_dataset="gnomad_sv_r4")
