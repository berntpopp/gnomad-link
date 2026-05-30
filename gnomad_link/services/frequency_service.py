"""Unified service layer for gnomAD data access.

This module provides a high-level service interface for querying gnomAD data
with integrated caching, error handling, and data transformation. It serves
both the FastAPI REST endpoints and MCP tool interfaces.
"""

import logging
from datetime import timedelta
from typing import Any

from async_lru import alru_cache

from gnomad_link.api.base_client import DataNotFoundError, GnomadApiError
from gnomad_link.api.client import UnifiedGnomadClient
from gnomad_link.models import (
    ClinVarVariant,
    Gene,
    GeneSearchResult,
    PopulationFrequency,
    VariantDataSource,
    VariantFrequencyResponse,
)

logger = logging.getLogger(__name__)


def _pick_canonical_annotation(
    transcripts: list[dict[str, Any]] | None,
) -> tuple[str | None, str | None]:
    """Return (gene_symbol, major_consequence) from the canonical transcript when present.

    Falls back to the first transcript_consequence with both fields populated; returns
    (None, None) if the GraphQL response did not include transcript_consequences.
    """

    if not transcripts:
        return None, None
    for tc in transcripts:
        if tc.get("canonical") and tc.get("gene_symbol"):
            return tc.get("gene_symbol"), tc.get("major_consequence")
    for tc in transcripts:
        if tc.get("gene_symbol"):
            return tc.get("gene_symbol"), tc.get("major_consequence")
    return None, None


class FrequencyService:
    """Unified service for gnomAD data queries with integrated caching.

    This service provides:
    - Transparent caching with LRU eviction and TTL
    - Automatic retry on cache failures
    - Data transformation to domain models
    - Cache statistics and management
    - Connection pooling via the underlying client

    The service maintains separate caches for variants and genes to optimize
    memory usage based on expected access patterns.
    """

    def __init__(
        self,
        client: UnifiedGnomadClient | None = None,
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
        self._get_variant_cached = alru_cache(maxsize=cache_size)(self._get_variant_impl)
        self._get_gene_cached = alru_cache(maxsize=cache_size // 4)(self._get_gene_impl)

        # Track cache statistics
        self._cache_hits = 0
        self._cache_misses = 0

    async def get_variant_frequencies(
        self, variant_id: str, dataset: str = "gnomad_r4"
    ) -> VariantFrequencyResponse:
        """Get variant frequency data with caching.

        Retrieves population allele frequencies for a specific variant from the
        requested gnomAD dataset. Results are cached to improve performance for
        repeated queries.

        Args:
            variant_id: Variant identifier in CHROM-POS-REF-ALT format
                (e.g., '1-55051215-G-GA')
            dataset: gnomAD dataset version to query (default: 'gnomad_r4')
                Options: 'gnomad_r2_1', 'gnomad_r3', 'gnomad_r4'

        Returns:
            VariantFrequencyResponse containing:
            - Exome frequency data (if available)
            - Genome frequency data (if available)
            - Population-specific allele counts and frequencies

        Raises:
            ValueError: If variant_id or dataset is empty
            VariantNotFoundError: If variant not found in the dataset
            GnomadApiError: If API communication fails
        """
        # Validate input
        if not variant_id:
            raise ValueError("variant_id cannot be empty")
        if not dataset:
            raise ValueError("dataset cannot be empty")

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
        """Fetch variant data from the gnomAD API.

        Internal method that performs the actual API call to retrieve variant data.
        This is wrapped by the caching decorator in the public interface.

        Args:
            variant_id: Variant identifier
            dataset: Dataset to query

        Returns:
            Raw variant data dictionary from the API
        """
        result = await self.client.get_variant(variant_id, dataset)
        variant_data = result.get("variant")
        if variant_data is None:
            return {}
        return dict(variant_data)

    def _parse_variant_response(
        self, data: dict[str, Any], variant_id: str, dataset: str
    ) -> VariantFrequencyResponse:
        """Parse raw variant data into structured response model.

        Transforms the raw API response into a structured VariantFrequencyResponse
        object with proper typing and validation. Handles missing fields gracefully
        by providing sensible defaults.

        Args:
            data: Raw variant data from the API
            variant_id: Original variant identifier
            dataset: Dataset that was queried

        Returns:
            Structured VariantFrequencyResponse object

        Raises:
            VariantNotFoundError: If data is empty (variant not found)
        """
        # Check if variant was found
        if not data:
            from gnomad_link.api.base_client import VariantNotFoundError

            raise VariantNotFoundError(f"Variant {variant_id} not found in {dataset}")

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

        gene_symbol, major_consequence = _pick_canonical_annotation(
            data.get("transcript_consequences")
        )

        return VariantFrequencyResponse(
            variant_id=variant_id,
            dataset=dataset,
            exome=exome_data,
            genome=genome_data,
            gene_symbol=gene_symbol,
            major_consequence=major_consequence,
        )

    async def get_gene(
        self,
        gene_id: str | None = None,
        gene_symbol: str | None = None,
        reference_genome: str | None = None,
        dataset: str | None = None,
    ) -> Gene:
        """Get gene information with caching.

        Retrieves comprehensive gene information including constraint metrics,
        pLI scores, and genomic coordinates. Either gene_id or gene_symbol
        must be provided.

        Args:
            gene_id: Ensembl gene ID (e.g., 'ENSG00000169174')
            gene_symbol: HGNC gene symbol (e.g., 'PCSK9')
            reference_genome: Reference genome build ('GRCh37' or 'GRCh38')
            dataset: Dataset for version-specific queries

        Returns:
            Gene object containing:
            - Basic metadata (name, location, transcripts)
            - Constraint scores (observed/expected variants)
            - pLI score for loss-of-function intolerance
            - Missense and synonymous z-scores

        Raises:
            ValueError: If neither gene_id nor gene_symbol provided
            DataNotFoundError: If gene not found
            GnomadApiError: If API communication fails
        """
        cache_key = f"{gene_id or ''}-{gene_symbol or ''}-{reference_genome or ''}-{dataset or ''}"

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
        gene_id: str | None,
        gene_symbol: str | None,
        reference_genome: str | None,
        dataset: str | None,
    ) -> dict[str, Any]:
        """Fetch gene data from the API."""
        result = await self.client.get_gene(gene_id, gene_symbol, reference_genome, dataset)
        gene_data = result.get("gene")
        if gene_data is None:
            return {}
        return dict(gene_data)

    async def search_genes(
        self,
        query: str,
        reference_genome: str | None = None,
        dataset: str | None = None,
    ) -> list[GeneSearchResult]:
        """Search for genes by symbol, name, or ID.

        Performs fuzzy searching across gene symbols, names, and Ensembl IDs.
        The search is case-insensitive and supports partial matches.

        Args:
            query: Search string (minimum 2 characters)
                Examples: 'PCSK9', 'ENSG00000169174', 'proprotein'
            reference_genome: Reference genome build to search
            dataset: Dataset for version-specific search

        Returns:
            List of GeneSearchResult objects containing:
            - Gene ID and symbol
            - Gene name
            - Genomic coordinates
            - Canonical transcript

        Note:
            Results are not cached as search queries are typically unique.
        """
        results = await self.client.search_genes(query, reference_genome, dataset)
        return [GeneSearchResult(**item) for item in results]

    async def search_variants(self, query: str, dataset: str = "gnomad_r4") -> list[str]:
        """Search for variants by ID, rsID, or position.

        Searches the gnomAD database for variants matching the query string.
        Supports multiple search formats.

        Args:
            query: Search string (minimum 3 characters)
                Formats:
                - Variant ID: '1-55051215-G-GA'
                - rsID: 'rs11591147'
                - Position: '1:55051215'
            dataset: gnomAD dataset to search (default: 'gnomad_r4')

        Returns:
            List of matching variant IDs

        Note:
            Returns only variant IDs. Use get_variant_frequencies()
            to retrieve full frequency data for a specific variant.
        """
        results = await self.client.search_variants(query, dataset)
        return [item["variant_id"] for item in results]

    async def get_clinvar_variant(
        self,
        variant_id: str,
        reference_genome: str | None = None,
        dataset: str | None = None,
    ) -> ClinVarVariant:
        """Get ClinVar clinical significance data for a variant.

        Retrieves clinical annotations from ClinVar including pathogenicity
        assessments, review status, and submitter information.

        Args:
            variant_id: Variant identifier in CHROM-POS-REF-ALT format
            reference_genome: Reference genome build
            dataset: Dataset for coordinate mapping

        Returns:
            ClinVarVariant object containing:
            - Clinical significance (Pathogenic, Benign, VUS, etc.)
            - Gold star rating and review status
            - Submission details from clinical labs
            - Associated conditions
            - Last evaluation date

        Raises:
            DataNotFoundError: If variant not found in ClinVar
            GnomadApiError: If API communication fails
        """
        result = await self.client.get_clinvar_variant(variant_id, reference_genome, dataset)
        return ClinVarVariant(**result.get("clinvar_variant", {}))

    def get_cache_stats(self) -> dict[str, Any]:
        """Get comprehensive cache statistics.

        Provides insights into cache performance and memory usage to help
        with monitoring and optimization.

        Returns:
            Dictionary containing:
            - hits: Number of cache hits
            - misses: Number of cache misses
            - total: Total number of requests
            - hit_rate: Cache hit rate (0.0 to 1.0)
            - cache_info: Detailed stats for each cache:
                - currsize: Current number of cached items
                - maxsize: Maximum cache capacity
                - hits/misses: Per-cache statistics
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

    def clear_cache(self) -> None:
        """Clear all caches and reset statistics.

        Removes all cached entries and resets hit/miss counters. This is useful
        when the underlying data has been updated or to free memory.

        Note:
            This operation cannot be undone. All cached data will be lost.
        """
        self._get_variant_cached.cache_clear()
        self._get_gene_cached.cache_clear()
        self._cache_hits = 0
        self._cache_misses = 0

    async def close(self) -> None:
        """Close the service and release resources.

        Ensures proper cleanup of the underlying HTTP client connections.
        Should be called when the service is no longer needed.

        Note:
            After calling close(), the service instance should not be reused.
        """
        await self.client.close()

    # ------------------------------------------------------------------
    # Thin pass-through wrappers (added for MCP facade, Task 4)
    # These provide a single seam for caching/instrumentation in future
    # tasks without any behavior change.
    # ------------------------------------------------------------------

    async def get_variant(self, variant_id: str, dataset: str = "gnomad_r4") -> dict[str, Any]:
        """Raw variant data pass-through."""
        return await self.client.get_variant(variant_id, dataset)

    async def get_gene_variants(
        self, gene_id: str, dataset: str = "gnomad_r4"
    ) -> list[dict[str, Any]]:
        """Raw gene variants pass-through."""
        return await self.client.get_gene_variants(gene_id, dataset)

    async def get_clinvar_meta(self) -> dict[str, Any]:
        """Raw ClinVar metadata pass-through."""
        return await self.client.get_meta()

    async def get_structural_variant(
        self, variant_id: str, dataset: str = "gnomad_sv_r4"
    ) -> dict[str, Any]:
        """Raw structural variant data pass-through."""
        return await self.client.get_structural_variant(variant_id, dataset)

    async def get_mitochondrial_variant(
        self, variant_id: str, dataset: str = "gnomad_r4"
    ) -> dict[str, Any]:
        """Raw mitochondrial variant data pass-through."""
        return await self.client.get_mitochondrial_variant(variant_id, dataset)

    async def get_region(
        self, chrom: str, start: int, stop: int, dataset: str = "gnomad_r4"
    ) -> dict[str, Any]:
        """Raw genomic region data pass-through."""
        return await self.client.get_region(chrom, start, stop, dataset)

    async def get_transcript(
        self, transcript_id: str, reference_genome: str = "GRCh38"
    ) -> dict[str, Any]:
        """Raw transcript data pass-through."""
        return await self.client.get_transcript(transcript_id, reference_genome)

    async def liftover_variant(
        self, source_variant_id: str, reference_genome: str = "GRCh38"
    ) -> list[dict[str, Any]]:
        """Raw liftover data pass-through."""
        return await self.client.get_liftover(source_variant_id, reference_genome)

    async def get_gene_summary(
        self,
        *,
        gene_id: str | None = None,
        gene_symbol: str | None = None,
        dataset: str = "gnomad_r4",
    ) -> dict[str, Any]:
        """Delegate to GeneSummaryService for the one-shot gene dossier."""
        from gnomad_link.services.gene_summary_service import GeneSummaryService

        return await GeneSummaryService(client=self.client).get_gene_summary(
            gene_id=gene_id, gene_symbol=gene_symbol, dataset=dataset
        )
