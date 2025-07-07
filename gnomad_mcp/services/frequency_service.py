"""Unified service layer for both FastAPI and MCP."""

import logging
from datetime import timedelta
from typing import Any, Optional

from async_lru import alru_cache

from gnomad_mcp.api.base_client import DataNotFoundError, GnomadApiError
from gnomad_mcp.api.client import UnifiedGnomadClient
from gnomad_mcp.models import (
    ClinVarVariant,
    Gene,
    GeneSearchResult,
    PopulationFrequency,
    VariantDataSource,
    VariantFrequencyResponse,
)

logger = logging.getLogger(__name__)


class FrequencyService:
    """Unified service for gnomAD data queries with caching."""

    def __init__(
        self,
        client: Optional[UnifiedGnomadClient] = None,
        cache_size: int = 1024,
        cache_ttl_minutes: int = 60,
    ):
        """Initialize the service.

        Args:
            client: Unified gnomAD API client instance
            cache_size: Maximum number of items to cache
            cache_ttl_minutes: Cache time-to-live in minutes
        """
        self.client = client or UnifiedGnomadClient()
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)

        # Configure caching
        self._get_variant_cached = alru_cache(maxsize=cache_size)(
            self._get_variant_impl
        )
        self._get_gene_cached = alru_cache(maxsize=cache_size // 4)(self._get_gene_impl)

        # Track cache statistics
        self._cache_hits = 0
        self._cache_misses = 0

    async def get_variant_frequencies(
        self, variant_id: str, dataset: str = "gnomad_r4"
    ) -> VariantFrequencyResponse:
        """Get variant frequency data with caching.

        Args:
            variant_id: Variant identifier
            dataset: Dataset to query

        Returns:
            Variant frequency response
        """
        try:
            data = await self._get_variant_cached(variant_id, dataset)
            self._cache_hits += 1
        except Exception as e:
            self._cache_misses += 1
            if isinstance(e, (GnomadApiError, DataNotFoundError)):
                raise
            # Re-fetch on cache error
            data = await self._get_variant_impl(variant_id, dataset)

        return self._parse_variant_response(data, variant_id, dataset)

    async def _get_variant_impl(self, variant_id: str, dataset: str) -> dict[str, Any]:
        """Fetch variant data from the API."""
        result = await self.client.get_variant(variant_id, dataset)
        return result.get("variant", {})

    def _parse_variant_response(
        self, data: dict[str, Any], variant_id: str, dataset: str
    ) -> VariantFrequencyResponse:
        """Parse variant data into response model."""
        # Parse exome data
        exome_data = None
        if data.get("exome"):
            exome_pops = []
            for pop_data in data["exome"].get("populations", []):
                exome_pops.append(
                    PopulationFrequency(
                        id=pop_data["id"],
                        ac=pop_data.get("ac", 0),
                        an=pop_data.get("an", 0),
                        homozygote_count=pop_data.get("homozygote_count", 0),
                    )
                )

            exome_data = VariantDataSource(
                ac=data["exome"].get("ac", 0),
                an=data["exome"].get("an", 0),
                homozygote_count=data["exome"].get("homozygote_count", 0),
                hemizygote_count=data["exome"].get("hemizygote_count", 0),
                populations=exome_pops,
            )

        # Parse genome data
        genome_data = None
        if data.get("genome"):
            genome_pops = []
            for pop_data in data["genome"].get("populations", []):
                genome_pops.append(
                    PopulationFrequency(
                        id=pop_data["id"],
                        ac=pop_data.get("ac", 0),
                        an=pop_data.get("an", 0),
                        homozygote_count=pop_data.get("homozygote_count", 0),
                    )
                )

            genome_data = VariantDataSource(
                ac=data["genome"].get("ac", 0),
                an=data["genome"].get("an", 0),
                homozygote_count=data["genome"].get("homozygote_count", 0),
                hemizygote_count=data["genome"].get("hemizygote_count", 0),
                populations=genome_pops,
            )

        return VariantFrequencyResponse(
            variant_id=variant_id,
            dataset=dataset,
            exome=exome_data,
            genome=genome_data,
        )

    async def get_gene(
        self,
        gene_id: Optional[str] = None,
        gene_symbol: Optional[str] = None,
        reference_genome: Optional[str] = None,
        dataset: Optional[str] = None,
    ) -> Gene:
        """Get gene information with caching.

        Args:
            gene_id: Ensembl gene ID
            gene_symbol: Gene symbol
            reference_genome: Reference genome
            dataset: Dataset (for version determination)

        Returns:
            Gene information
        """
        cache_key = (
            f"{gene_id or ''}-{gene_symbol or ''}-"
            f"{reference_genome or ''}-{dataset or ''}"
        )

        try:
            data = await self._get_gene_cached(
                cache_key, gene_id, gene_symbol, reference_genome, dataset
            )
            self._cache_hits += 1
        except Exception as e:
            self._cache_misses += 1
            if isinstance(e, (GnomadApiError, DataNotFoundError)):
                raise
            data = await self._get_gene_impl(
                cache_key, gene_id, gene_symbol, reference_genome, dataset
            )

        return Gene(**data)

    async def _get_gene_impl(
        self,
        cache_key: str,
        gene_id: Optional[str],
        gene_symbol: Optional[str],
        reference_genome: Optional[str],
        dataset: Optional[str],
    ) -> dict[str, Any]:
        """Fetch gene data from the API."""
        result = await self.client.get_gene(
            gene_id, gene_symbol, reference_genome, dataset
        )
        return result.get("gene", {})

    async def search_genes(
        self,
        query: str,
        reference_genome: Optional[str] = None,
        dataset: Optional[str] = None,
    ) -> list[GeneSearchResult]:
        """Search for genes.

        Args:
            query: Search query
            reference_genome: Reference genome
            dataset: Dataset (for version determination)

        Returns:
            List of gene search results
        """
        results = await self.client.search_genes(query, reference_genome, dataset)
        return [GeneSearchResult(**item) for item in results]

    async def search_variants(
        self, query: str, dataset: str = "gnomad_r4"
    ) -> list[str]:
        """Search for variants.

        Args:
            query: Search query
            dataset: Dataset to search

        Returns:
            List of variant IDs
        """
        results = await self.client.search_variants(query, dataset)
        return [item["variant_id"] for item in results]

    async def get_clinvar_variant(
        self,
        variant_id: str,
        reference_genome: Optional[str] = None,
        dataset: Optional[str] = None,
    ) -> ClinVarVariant:
        """Get ClinVar variant data.

        Args:
            variant_id: Variant identifier
            reference_genome: Reference genome
            dataset: Dataset (for version determination)

        Returns:
            ClinVar variant information
        """
        result = await self.client.get_clinvar_variant(
            variant_id, reference_genome, dataset
        )
        return ClinVarVariant(**result.get("clinvar_variant", {}))

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Cache statistics
        """
        total = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total if total > 0 else 0.0

        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "total": total,
            "hit_rate": round(hit_rate, 3),
            "cache_info": {
                "variant": self._get_variant_cached.cache_info()._asdict(),
                "gene": self._get_gene_cached.cache_info()._asdict(),
            },
        }

    def clear_cache(self):
        """Clear all caches."""
        self._get_variant_cached.cache_clear()
        self._get_gene_cached.cache_clear()
        self._cache_hits = 0
        self._cache_misses = 0

    async def close(self):
        """Close the service and underlying connections."""
        await self.client.close()
