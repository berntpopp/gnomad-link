"""Unified gnomAD client for both FastAPI and MCP."""

from typing import Any

from gnomad_link.graphql import QueryBuilder

from .base_client import BaseGnomadClient


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

    async def get_transcript_gtex(
        self, transcript_id: str, reference_genome: str = "GRCh37"
    ) -> dict[str, Any]:
        """Fetch only GTEx tissue expression for a transcript (GRCh37-populated)."""
        variables = {
            "transcript_id": transcript_id,
            "reference_genome": reference_genome,
        }
        return await self.execute_query("transcript_gtex", variables, "v2")

    async def get_liftover(
        self,
        source_variant_id: str,
        reference_genome: str = "GRCh38",
    ) -> list[dict[str, Any]]:
        """Get liftover mapping between reference genomes.

        Args:
            source_variant_id: Variant ID to liftover
            reference_genome: Source reference genome of the variant

        Returns:
            List of liftover results (may be empty if no mapping exists)
        """
        variables = {
            "source_variant_id": source_variant_id,
            "reference_genome": reference_genome,
        }

        result = await self.execute_query("liftover", variables)
        return list(result.get("liftover", []))
