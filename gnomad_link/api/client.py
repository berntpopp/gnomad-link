"""Unified gnomAD client for both FastAPI and MCP."""

import asyncio
from typing import Any

from gnomad_link.graphql import QueryBuilder

from .base_client import BaseGnomadClient

# gnomAD enforces a per-query cost limit of 25 (one unit per clinvar_variant
# alias). Batches must stay at or below it; 24 leaves a one-unit safety margin.
# (The gnomad-carrier-frequency reference uses 50, which now fails every batch.)
_CLINVAR_SUBMISSIONS_BATCH_SIZE = 24


class ClinvarSubmissionsBatchResult(dict[str, list[dict[str, Any]]]):
    """Dict-compatible batch result with degradation counters."""

    def __init__(
        self,
        *args: Any,
        failed_chunks: int = 0,
        failed_variant_ids: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.failed_chunks = failed_chunks
        self.failed_variant_ids = failed_variant_ids or []


def _build_clinvar_submissions_query(variant_ids: list[str], reference_genome: str) -> str:
    """Aliased batch query for ClinVar submissions (one alias per variant).

    Ports gnomad-carrier-frequency's buildSubmissionsQuery. Variant ids are
    inlined as string literals (they contain '-'); reference_genome is a GraphQL
    enum (unquoted). Callers pass only gnomAD-sourced ids, so this is not an
    injection surface.
    """
    parts = [
        f'v{i}: clinvar_variant(variant_id: "{vid}", reference_genome: {reference_genome}) '
        "{ variant_id submissions { clinical_significance } }"
        for i, vid in enumerate(variant_ids)
    ]
    return "query ClinVarSubmissions {\n" + "\n".join(parts) + "\n}"


class UnifiedGnomadClient(BaseGnomadClient):
    """Unified client supporting all gnomAD queries for both FastAPI and MCP."""

    async def get_variant(self, variant_id: str, dataset: str = "gnomad_r4") -> dict[str, Any]:
        """Get variant data.

        Args:
            variant_id: Variant identifier (chr-pos-ref-alt)
            dataset: Dataset to query

        Returns:
            Variant data
        """
        version = QueryBuilder.get_version_for_dataset(dataset)
        return await self.execute_query(
            "variant", {"variantId": variant_id, "dataset": dataset}, version
        )

    async def get_gene(
        self,
        gene_id: str | None = None,
        gene_symbol: str | None = None,
        reference_genome: str | None = None,
        dataset: str | None = None,
    ) -> dict[str, Any]:
        """Get gene data.

        Args:
            gene_id: Ensembl gene ID
            gene_symbol: Gene symbol
            reference_genome: Reference genome (optional, auto-determined)
            dataset: Dataset (optional, for version determination)

        Returns:
            Gene data
        """
        # Determine version
        version = "v4"
        if dataset:
            version = QueryBuilder.get_version_for_dataset(dataset)

        # Build variables
        variables = {}
        if gene_id:
            variables["gene_id"] = gene_id
        if gene_symbol:
            variables["gene_symbol"] = gene_symbol
        if reference_genome:
            variables["reference_genome"] = reference_genome

        # Process variables to add reference genome if needed
        processed_vars = self.query_builder.process_variables("gene", variables, version)

        return await self.execute_query("gene", processed_vars, version)

    async def get_gene_summary(
        self,
        *,
        gene_id: str | None = None,
        gene_symbol: str | None = None,
        reference_genome: str | None = None,
        dataset: str | None = None,
    ) -> dict[str, Any]:
        """Get the gene-summary payload (constraint + MANE + clinvar_variants + pext).

        Args:
            gene_id: Ensembl gene ID
            gene_symbol: Gene symbol
            reference_genome: Reference genome (optional, auto-determined from dataset)
            dataset: Dataset (optional, for version determination)

        Returns:
            Raw gene_summary query result keyed by "gene"
        """
        version = "v4"
        if dataset:
            version = QueryBuilder.get_version_for_dataset(dataset)

        variables: dict[str, Any] = {}
        if gene_id:
            variables["gene_id"] = gene_id
        if gene_symbol:
            variables["gene_symbol"] = gene_symbol
        if reference_genome:
            variables["reference_genome"] = reference_genome

        processed_vars = self.query_builder.process_variables("gene_summary", variables, version)
        return await self.execute_query("gene_summary", processed_vars, version)

    async def search_variants(self, query: str, dataset: str = "gnomad_r4") -> list[dict[str, Any]]:
        """Search for variants.

        Args:
            query: Search query
            dataset: Dataset to search

        Returns:
            List of variant search results
        """
        version = QueryBuilder.get_version_for_dataset(dataset)
        result = await self.execute_query(
            "variant_search", {"query": query, "dataset": dataset}, version
        )
        return list(result.get("variant_search", []))

    async def search_genes(
        self,
        query: str,
        reference_genome: str | None = None,
        dataset: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for genes.

        Args:
            query: Search query
            reference_genome: Reference genome (optional)
            dataset: Dataset (optional, for version determination)

        Returns:
            List of gene search results
        """
        version = "v4"
        if dataset:
            version = QueryBuilder.get_version_for_dataset(dataset)

        variables = {"query": query}
        if reference_genome:
            variables["reference_genome"] = reference_genome

        result = await self.execute_query("gene_search", variables, version)
        return list(result.get("gene_search", []))

    async def get_clinvar_variant(
        self,
        variant_id: str,
        reference_genome: str | None = None,
        dataset: str | None = None,
    ) -> dict[str, Any]:
        """Get ClinVar variant data.

        Args:
            variant_id: Variant identifier
            reference_genome: Reference genome (optional)
            dataset: Dataset (optional, for version determination)

        Returns:
            ClinVar variant data
        """
        version = "v4"
        if dataset:
            version = QueryBuilder.get_version_for_dataset(dataset)

        variables = {"variant_id": variant_id}
        if reference_genome:
            variables["reference_genome"] = reference_genome

        return await self.execute_query("clinvar_variant", variables, version)

    async def get_meta(self) -> dict[str, Any]:
        """Get metadata about the gnomAD database.

        Returns:
            Metadata
        """
        return await self.execute_query("meta", {})

    async def get_clinvar_submissions_batch(
        self,
        variant_ids: list[str],
        reference_genome: str = "GRCh38",
        *,
        batch_size: int = _CLINVAR_SUBMISSIONS_BATCH_SIZE,
    ) -> ClinvarSubmissionsBatchResult:
        """Fetch ClinVar submissions for many variants via aliased batch queries.

        One upstream request per ``batch_size`` variants (<= the gnomAD query-cost
        limit), with batches fired concurrently and bounded by the client
        semaphore + exponential-backoff retry. Returns
        ``{variant_id: [{clinical_significance}, ...]}``; variants absent from
        ClinVar are omitted. Each batch is best-effort: a failed batch contributes
        nothing rather than failing the whole resolution, and increments
        ``failed_chunks`` / ``failed_variant_ids`` on the dict-compatible result.
        """
        if not variant_ids:
            return ClinvarSubmissionsBatchResult()
        chunks = [variant_ids[i : i + batch_size] for i in range(0, len(variant_ids), batch_size)]

        async def fetch(chunk: list[str]) -> ClinvarSubmissionsBatchResult:
            query = _build_clinvar_submissions_query(chunk, reference_genome)
            try:
                data = await self.execute_raw_query(query)
            except Exception:
                return ClinvarSubmissionsBatchResult(
                    failed_chunks=1, failed_variant_ids=list(chunk)
                )
            out: dict[str, list[dict[str, Any]]] = {}
            for value in data.values():
                if isinstance(value, dict) and value.get("variant_id"):
                    out[str(value["variant_id"])] = value.get("submissions") or []
            return ClinvarSubmissionsBatchResult(out)

        merged = ClinvarSubmissionsBatchResult()
        for result in await asyncio.gather(*(fetch(chunk) for chunk in chunks)):
            merged.update(result)
            merged.failed_chunks += result.failed_chunks
            merged.failed_variant_ids.extend(result.failed_variant_ids)
        return merged

    async def get_structural_variant(
        self, variant_id: str, dataset: str = "gnomad_sv_r4"
    ) -> dict[str, Any]:
        """Get structural variant data.

        Args:
            variant_id: Structural variant identifier
            dataset: SV dataset to query

        Returns:
            Structural variant data
        """
        version = QueryBuilder.get_version_for_dataset(dataset)
        return await self.execute_query(
            "structural_variant",
            {"variant_id": variant_id, "dataset": dataset},
            version,
        )

    async def get_mitochondrial_variant(
        self, variant_id: str, dataset: str = "gnomad_r4"
    ) -> dict[str, Any]:
        """Get mitochondrial variant data.

        Args:
            variant_id: Mitochondrial variant identifier
            dataset: Dataset to query

        Returns:
            Mitochondrial variant data
        """
        version = QueryBuilder.get_version_for_dataset(dataset)
        return await self.execute_query(
            "mitochondrial_variant",
            {"variant_id": variant_id, "dataset": dataset},
            version,
        )

    async def get_region(
        self, chrom: str, start: int, stop: int, dataset: str = "gnomad_r4"
    ) -> dict[str, Any]:
        """Get data for a genomic region.

        Args:
            chrom: Chromosome
            start: Start position
            stop: Stop position
            dataset: Dataset to query

        Returns:
            Region data including variants and genes
        """
        version = QueryBuilder.get_version_for_dataset(dataset)
        # Don't include dataset in variables - it's not used in the simplified query
        return await self.execute_query(
            "region",
            {"chrom": chrom, "start": start, "stop": stop},
            version,
        )

    async def get_transcript(
        self,
        transcript_id: str,
        reference_genome: str | None = None,
        dataset: str | None = None,
    ) -> dict[str, Any]:
        """Get transcript data.

        Args:
            transcript_id: Ensembl transcript ID
            reference_genome: Reference genome (optional)
            dataset: Dataset (optional, for version determination)

        Returns:
            Transcript data
        """
        version = "v4"
        if dataset:
            version = QueryBuilder.get_version_for_dataset(dataset)

        variables = {"transcript_id": transcript_id}
        if reference_genome:
            variables["reference_genome"] = reference_genome

        return await self.execute_query("transcript", variables, version)

    async def get_gene_variants(
        self, gene_id: str, dataset: str = "gnomad_r4"
    ) -> list[dict[str, Any]]:
        """Get all variants in a gene.

        Args:
            gene_id: Ensembl gene ID
            dataset: Dataset to query

        Returns:
            List of variants in the gene
        """
        version = QueryBuilder.get_version_for_dataset(dataset)
        # Process variables to add reference genome
        variables = {"gene_id": gene_id, "dataset": dataset}
        processed_vars = self.query_builder.process_variables("gene_variants", variables, version)

        result = await self.execute_query("gene_variants", processed_vars, version)
        # Extract variants from nested structure
        if "gene" in result and "variants" in result["gene"]:
            return list(result["gene"]["variants"])
        return []

    async def get_gene_carrier_variants(
        self,
        *,
        gene_id: str | None = None,
        gene_symbol: str | None = None,
        dataset: str = "gnomad_r4",
    ) -> dict[str, Any]:
        """Fetch enriched gene variants + clinvar for gene-level carrier frequency.

        Returns the raw ``{"gene": {...}}`` payload (variants with per-population
        ac/an/homozygote_count + transcript_consequence LOFTEE, plus the parallel
        clinvar_variants array). One call covers a whole gene (~500 variants).
        """
        version = QueryBuilder.get_version_for_dataset(dataset)
        reference_genome = QueryBuilder.get_reference_genome(version)
        variables: dict[str, Any] = {
            "dataset": dataset,
            "reference_genome": reference_genome,
        }
        if gene_id:
            variables["gene_id"] = gene_id
        if gene_symbol:
            variables["gene_symbol"] = gene_symbol
        return await self.execute_query("gene_carrier_variants", variables, version)

    async def get_gene_gtex(
        self,
        *,
        gene_id: str | None = None,
        gene_symbol: str | None = None,
        reference_genome: str = "GRCh38",
    ) -> dict[str, Any]:
        """Fetch GTEx tissue expression via the gene's transcripts.

        GTEx is exposed on ``gene.transcripts[].gtex_tissue_expression``. The
        standalone ``transcript(transcript_id).gtex_tissue_expression`` field is
        unavailable on GRCh38 and errors upstream on GRCh37, so the gene path is
        the only working source.
        """
        variables: dict[str, Any] = {"reference_genome": reference_genome}
        if gene_id:
            variables["gene_id"] = gene_id
        if gene_symbol:
            variables["gene_symbol"] = gene_symbol
        return await self.execute_query("gene_gtex", variables, "v4")

    async def get_liftover(
        self,
        source_variant_id: str,
        reference_genome: str = "GRCh38",
    ) -> list[dict[str, Any]]:
        """Get liftover mapping between reference genomes (bidirectional).

        gnomAD's liftover table is keyed on the GRCh37 ``source`` coordinate, so
        a GRCh38 input is the liftover *target*, not the source. Querying it via
        ``source_variant_id`` therefore returns nothing. To recover the GRCh37
        coordinate we must query by ``liftover_variant_id`` instead. The variant
        id is the same; only the argument it binds to changes with direction.

        Args:
            source_variant_id: Variant ID to convert (in ``reference_genome``).
            reference_genome: Reference build of ``source_variant_id``.

        Returns:
            List of liftover records (each with both ``source`` GRCh37 and
            ``liftover`` GRCh38 entries); empty when no mapping exists.
        """
        variables: dict[str, Any] = {"reference_genome": reference_genome}
        if reference_genome == "GRCh38":
            # Reverse direction (GRCh38 -> GRCh37): the input is the liftover target.
            variables["liftover_variant_id"] = source_variant_id
        else:
            # Forward direction (GRCh37 -> GRCh38): the input is the source.
            variables["source_variant_id"] = source_variant_id

        result = await self.execute_query("liftover", variables)
        return list(result.get("liftover", []))

    async def search_structural_variants_by_gene(
        self,
        *,
        gene_id: str | None,
        gene_symbol: str | None,
        reference_genome: str,
        sv_dataset: str = "gnomad_sv_r4",
    ) -> list[dict[str, Any]]:
        """Search structural variants overlapping a gene.

        Args:
            gene_id: Ensembl gene ID (mutually exclusive with gene_symbol)
            gene_symbol: HGNC gene symbol
            reference_genome: GRCh37 or GRCh38 (derived from sv_dataset)
            sv_dataset: StructuralVariantDatasetId enum value

        Returns:
            Flat list of structural variant rows (may be empty)
        """
        variables: dict[str, Any] = {
            "gene_id": gene_id,
            "gene_symbol": gene_symbol,
            "reference_genome": reference_genome,
            "sv_dataset": sv_dataset,
        }
        result = await self.execute_query("sv_search_by_gene", variables, "v4")
        gene = result.get("gene") or {}
        return list(gene.get("structural_variants") or [])

    async def search_structural_variants_by_region(
        self,
        *,
        chrom: str,
        start: int,
        stop: int,
        reference_genome: str,
        sv_dataset: str = "gnomad_sv_r4",
    ) -> list[dict[str, Any]]:
        """Search structural variants overlapping a region.

        Args:
            chrom: Chromosome (no chr prefix)
            start: 1-based start position
            stop: 1-based stop position
            reference_genome: GRCh37 or GRCh38 (derived from sv_dataset)
            sv_dataset: StructuralVariantDatasetId enum value

        Returns:
            Flat list of structural variant rows (may be empty)
        """
        variables: dict[str, Any] = {
            "chrom": chrom,
            "start": start,
            "stop": stop,
            "reference_genome": reference_genome,
            "sv_dataset": sv_dataset,
        }
        result = await self.execute_query("sv_search_by_region", variables, "v4")
        region = result.get("region") or {}
        return list(region.get("structural_variants") or [])

    async def get_gene_coverage(
        self,
        *,
        gene_id: str | None,
        gene_symbol: str | None,
        reference_genome: str,
        dataset: str,
    ) -> dict[str, Any]:
        """Get per-position exome/genome coverage bins for a gene."""
        version = QueryBuilder.get_version_for_dataset(dataset)
        variables: dict[str, Any] = {
            "reference_genome": reference_genome,
            "dataset": dataset,
        }
        if gene_id:
            variables["gene_id"] = gene_id
        if gene_symbol:
            variables["gene_symbol"] = gene_symbol
        return await self.execute_query("coverage_gene", variables, version)

    async def get_region_coverage(
        self,
        *,
        chrom: str,
        start: int,
        stop: int,
        reference_genome: str,
        dataset: str,
    ) -> dict[str, Any]:
        """Get per-position exome/genome coverage bins for a region."""
        version = QueryBuilder.get_version_for_dataset(dataset)
        variables: dict[str, Any] = {
            "chrom": chrom,
            "start": start,
            "stop": stop,
            "reference_genome": reference_genome,
            "dataset": dataset,
        }
        return await self.execute_query("coverage_region", variables, version)

    async def get_variant_coverage(self, *, variant_id: str, dataset: str) -> dict[str, Any]:
        """Get scalar exome/genome coverage for a single variant."""
        version = QueryBuilder.get_version_for_dataset(dataset)
        variables: dict[str, Any] = {"variantId": variant_id, "dataset": dataset}
        return await self.execute_query("coverage_variant", variables, version)
