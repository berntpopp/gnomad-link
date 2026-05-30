from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.services.coverage_service import CoverageService


class _StubClient:
    def __init__(self) -> None:
        self.gene_calls: list[tuple[Any, ...]] = []
        self.region_calls: list[tuple[Any, ...]] = []
        self.variant_calls: list[tuple[Any, ...]] = []

    async def get_gene_coverage(
        self,
        *,
        gene_id: str | None,
        gene_symbol: str | None,
        reference_genome: str,
        dataset: str,
    ) -> dict[str, Any]:
        self.gene_calls.append((gene_id, gene_symbol, reference_genome, dataset))
        return {
            "gene": {
                "gene_id": gene_id or "ENSG00000169174",
                "symbol": gene_symbol or "PCSK9",
                "coverage": {
                    "exome": [
                        {"pos": 100, "mean": 31.2, "median": 30, "over_20": 0.99, "over_30": 0.81}
                    ],
                    "genome": [
                        {"pos": 100, "mean": 28.0, "median": 28, "over_20": 0.97, "over_30": 0.6}
                    ],
                },
            }
        }

    async def get_region_coverage(
        self,
        *,
        chrom: str,
        start: int,
        stop: int,
        reference_genome: str,
        dataset: str,
    ) -> dict[str, Any]:
        self.region_calls.append((chrom, start, stop, reference_genome, dataset))
        return {
            "region": {
                "chrom": chrom,
                "start": start,
                "stop": stop,
                "coverage": {
                    "exome": [
                        {"pos": start, "mean": 30.0, "median": 30, "over_20": 0.98, "over_30": 0.7}
                    ],
                    "genome": [],
                },
            }
        }

    async def get_variant_coverage(self, *, variant_id: str, dataset: str) -> dict[str, Any]:
        self.variant_calls.append((variant_id, dataset))
        return {
            "variant": {
                "variant_id": variant_id,
                "coverage": {
                    "exome": {"mean": 31.0, "median": 31, "over_20": 0.99, "over_30": 0.82},
                    "genome": {"mean": 27.0, "median": 27, "over_20": 0.95, "over_30": 0.55},
                },
            }
        }


@pytest.mark.asyncio
async def test_get_gene_coverage_maps_reference_genome_from_dataset() -> None:
    client = _StubClient()
    service = CoverageService(client=client)

    raw = await service.get_gene_coverage(gene_id=None, gene_symbol="PCSK9", dataset="gnomad_r4")

    assert client.gene_calls == [(None, "PCSK9", "GRCh38", "gnomad_r4")]
    assert raw["gene"]["coverage"]["exome"][0]["mean"] == 31.2


@pytest.mark.asyncio
async def test_get_gene_coverage_uses_grch37_for_r2_1() -> None:
    client = _StubClient()
    service = CoverageService(client=client)

    await service.get_gene_coverage(
        gene_id="ENSG00000169174", gene_symbol=None, dataset="gnomad_r2_1"
    )

    assert client.gene_calls == [("ENSG00000169174", None, "GRCh37", "gnomad_r2_1")]


@pytest.mark.asyncio
async def test_get_region_coverage_passes_reference_genome_and_dataset() -> None:
    client = _StubClient()
    service = CoverageService(client=client)

    await service.get_region_coverage(
        chrom="1", start=55_039_447, stop=55_039_547, dataset="gnomad_r4"
    )

    assert client.region_calls == [("1", 55_039_447, 55_039_547, "GRCh38", "gnomad_r4")]


@pytest.mark.asyncio
async def test_get_variant_coverage_passes_dataset_only() -> None:
    client = _StubClient()
    service = CoverageService(client=client)

    raw = await service.get_variant_coverage(variant_id="1-55039447-A-G", dataset="gnomad_r4")

    assert client.variant_calls == [("1-55039447-A-G", "gnomad_r4")]
    assert raw["variant"]["coverage"]["exome"]["mean"] == 31.0
