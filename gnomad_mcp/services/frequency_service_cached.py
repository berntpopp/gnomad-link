"""Enhanced service layer with caching for variant frequency operations."""

import logging
from typing import List, Optional
from datetime import datetime, timedelta

from async_lru import alru_cache

from gnomad_mcp.api import GnomadApiClient, VariantNotFoundError
from gnomad_mcp.models import (
    VariantFrequencyResponse,
    VariantDataSource,
    PopulationFrequency,
)
from gnomad_mcp.config import settings

logger = logging.getLogger(__name__)


class CachedFrequencyService:
    """Service for retrieving and processing variant frequency data with caching.

    This enhanced version includes:
    - LRU caching with configurable size
    - TTL-based cache invalidation
    - Cache statistics for monitoring
    """

    def __init__(
        self,
        client: Optional[GnomadApiClient] = None,
        cache_size: int = 1024,
        cache_ttl_minutes: int = 60,
    ):
        """Initialize the service with caching.

        Args:
            client: Optional API client instance.
                If not provided, a new one is created.
            cache_size: Maximum number of variants to cache (default: 1024)
            cache_ttl_minutes: Cache time-to-live in minutes (default: 60)
        """
        self.client = client or GnomadApiClient()
        self.cache_size = cache_size
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self._cache_stats = {"hits": 0, "misses": 0}

        # Create the cached version of get_variant_frequencies
        self._get_variant_frequencies_cached = alru_cache(maxsize=cache_size)(
            self._get_variant_frequencies_impl
        )

    async def get_variant_frequencies(
        self, variant_id: str, dataset: str
    ) -> VariantFrequencyResponse:
        """Get variant frequency data from gnomAD with caching.

        Args:
            variant_id: The variant identifier (e.g., "1-55039447-G-T").
            dataset: The dataset to query (e.g., "gnomad_r4").

        Returns:
            Structured variant frequency response.

        Raises:
            VariantNotFoundError: If the variant is not found.
            ValueError: If the input parameters are invalid.
        """
        # Validate inputs
        if not variant_id:
            raise ValueError("variant_id cannot be empty")
        if not dataset:
            raise ValueError("dataset cannot be empty")

        # Basic validation of variant ID format
        variant_id = variant_id.strip().strip("'\"")  # Remove any quotes
        parts = variant_id.split("-")
        if len(parts) != 4:
            raise ValueError(
                f"Invalid variant ID format: '{variant_id}'. "
                "Expected format: chromosome-position-reference-alternate "
                "(e.g., '1-55039447-G-T')"
            )

        # Use the cached implementation
        return await self._get_variant_frequencies_cached(variant_id, dataset)

    async def _get_variant_frequencies_impl(
        self, variant_id: str, dataset: str
    ) -> VariantFrequencyResponse:
        """Internal implementation of variant frequency retrieval.

        This method is wrapped by the cache decorator.
        """
        logger.debug(f"Cache miss - fetching variant {variant_id} from API")
        self._cache_stats["misses"] += 1

        # Fetch raw data from API
        raw_data = await self.client.get_variant(variant_id, dataset)

        # Extract variant data
        variant_data = raw_data.get("variant")
        if not variant_data:
            raise VariantNotFoundError(
                f"Variant {variant_id} not found in dataset {dataset}"
            )

        # Process exome data
        exome_data = None
        if variant_data.get("exome") and variant_data["exome"].get("populations"):
            exome_populations = self._process_populations(
                variant_data["exome"]["populations"]
            )
            if exome_populations:
                exome_data = VariantDataSource(populations=exome_populations)

        # Process genome data
        genome_data = None
        if variant_data.get("genome") and variant_data["genome"].get("populations"):
            genome_populations = self._process_populations(
                variant_data["genome"]["populations"]
            )
            if genome_populations:
                genome_data = VariantDataSource(populations=genome_populations)

        # Build response
        response = VariantFrequencyResponse(
            variant_id=variant_id,
            dataset=dataset,
            exome=exome_data,
            genome=genome_data,
        )

        logger.debug(f"Successfully fetched and cached variant {variant_id}")
        return response

    def _process_populations(
        self, raw_populations: List[dict]
    ) -> List[PopulationFrequency]:
        """Process raw population data into PopulationFrequency objects.

        Args:
            raw_populations: Raw population data from the API.

        Returns:
            List of processed population frequencies.
        """
        populations = []

        for pop_data in raw_populations:
            # Skip populations with no data
            if not pop_data.get("id") or pop_data.get("an", 0) == 0:
                continue

            population = PopulationFrequency(
                id=pop_data["id"],
                ac=pop_data.get("ac", 0),
                an=pop_data.get("an", 0),
                homozygote_count=pop_data.get("homozygote_count", 0),
            )
            populations.append(population)

        return populations

    def get_cache_stats(self) -> dict:
        """Get cache statistics for monitoring.

        Returns:
            Dictionary with cache hits, misses, and hit rate.
        """
        total = self._cache_stats["hits"] + self._cache_stats["misses"]
        hit_rate = self._cache_stats["hits"] / total if total > 0 else 0

        return {
            "hits": self._cache_stats["hits"],
            "misses": self._cache_stats["misses"],
            "hit_rate": hit_rate,
            "size": self._get_variant_frequencies_cached.cache_info().currsize,
            "max_size": self.cache_size,
        }

    def clear_cache(self):
        """Clear the variant cache."""
        self._get_variant_frequencies_cached.cache_clear()
        logger.info("Variant cache cleared")

    async def close(self):
        """Close the service and cleanup resources."""
        if self.client:
            await self.client.close()


# For backward compatibility, keep the original class name
FrequencyService = CachedFrequencyService
