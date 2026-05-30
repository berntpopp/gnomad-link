"""Service layer for gnomAD read-depth coverage (gene, region, variant scopes)."""

from __future__ import annotations

from typing import Any

from gnomad_link.api.base_client import DataNotFoundError
from gnomad_link.api.client import UnifiedGnomadClient


def _reference_genome_for(dataset: str) -> str:
    """gnomad_r2_1 is GRCh37; r3/r4 are GRCh38."""
    return "GRCh37" if dataset == "gnomad_r2_1" else "GRCh38"


class CoverageService:
    """Fetch coverage payloads from the unified client.

    Thin orchestration: maps dataset -> reference build, calls the matching
    client method, and raises DataNotFoundError when the feature is absent so
    callers get the structured not_found envelope.
    """

    def __init__(self, client: UnifiedGnomadClient | None = None) -> None:
        self.client = client or UnifiedGnomadClient()

    async def get_gene_coverage(
        self, *, gene_id: str | None, gene_symbol: str | None, dataset: str
    ) -> dict[str, Any]:
        raw = await self.client.get_gene_coverage(
            gene_id=gene_id,
            gene_symbol=gene_symbol,
            reference_genome=_reference_genome_for(dataset),
            dataset=dataset,
        )
        if not (raw.get("gene") or {}).get("coverage"):
            raise DataNotFoundError(f"No coverage for gene {gene_id or gene_symbol} in {dataset}")
        return raw

    async def get_region_coverage(
        self, *, chrom: str, start: int, stop: int, dataset: str
    ) -> dict[str, Any]:
        raw = await self.client.get_region_coverage(
            chrom=chrom,
            start=start,
            stop=stop,
            reference_genome=_reference_genome_for(dataset),
            dataset=dataset,
        )
        if not (raw.get("region") or {}).get("coverage"):
            raise DataNotFoundError(f"No coverage for region {chrom}-{start}-{stop} in {dataset}")
        return raw

    async def get_variant_coverage(self, *, variant_id: str, dataset: str) -> dict[str, Any]:
        raw = await self.client.get_variant_coverage(variant_id=variant_id, dataset=dataset)
        if not (raw.get("variant") or {}).get("coverage"):
            raise DataNotFoundError(f"No coverage for variant {variant_id} in {dataset}")
        return raw
