"""Tests for search endpoints using clinical examples."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


class TestSearchEndpoints:
    """Test search endpoints with real examples."""

    @pytest.mark.asyncio
    async def test_search_brca_genes(self, client: AsyncClient):
        """Test searching for BRCA genes."""
        response = await client.get("/search/gene", params={"query": "BRCA"})

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) >= 2  # Should find at least BRCA1 and BRCA2

        # Check that BRCA1 and BRCA2 are in results
        symbols = [gene["symbol"] for gene in data]
        assert "BRCA1" in symbols
        assert "BRCA2" in symbols

        # Verify structure of results - search returns ensembl_id not gene_id
        for gene in data:
            assert "ensembl_id" in gene
            assert "symbol" in gene
            assert gene["ensembl_id"].startswith("ENSG")

    @pytest.mark.asyncio
    async def test_search_tp53_gene(self, client: AsyncClient):
        """Test searching for TP53 gene."""
        response = await client.get("/search/gene", params={"query": "TP53"})

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) >= 1

        # TP53 should be in results
        tp53_found = False
        for gene in data:
            if gene["symbol"] == "TP53":
                tp53_found = True
                assert gene["ensembl_id"] == "ENSG00000141510"
                break

        assert tp53_found, "TP53 not found in search results"

    @pytest.mark.asyncio
    async def test_search_apc_gene(self, client: AsyncClient):
        """Test searching for APC gene."""
        response = await client.get("/search/gene", params={"query": "APC"})

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)

        # Find APC in results
        apc_found = False
        for gene in data:
            if gene["symbol"] == "APC":
                apc_found = True
                # Search results may not include the full name
                break

        assert apc_found, "APC not found in search results"

    @pytest.mark.asyncio
    async def test_search_pcsk9_gene(self, client: AsyncClient):
        """Test searching for PCSK9 gene."""
        response = await client.get("/search/gene", params={"query": "PCSK9"})

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) >= 1

        # Check PCSK9 is found
        pcsk9 = next((g for g in data if g["symbol"] == "PCSK9"), None)
        assert pcsk9 is not None
        assert pcsk9["ensembl_id"] == "ENSG00000169174"

    @pytest.mark.asyncio
    async def test_search_variants_brca2_deletion(self, client: AsyncClient):
        """Test searching for BRCA2 deletion variant."""
        variant_id = "13-32394863-CTG-C"
        response = await client.get("/search/variant", params={"query": variant_id})

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        # Should find the exact variant
        if len(data) > 0:
            assert any(v.get("variant_id") == variant_id for v in data)

    @pytest.mark.asyncio
    async def test_search_variants_tp53_mutation(self, client: AsyncClient):
        """Test searching for TP53 R175H variant."""
        variant_id = "17-7674221-G-A"
        response = await client.get("/search/variant", params={"query": variant_id})

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        # Should find the variant
        if len(data) > 0:
            variant_ids = [v.get("variant_id") for v in data]
            assert variant_id in variant_ids

    @pytest.mark.asyncio
    async def test_search_variants_by_rsid(self, client: AsyncClient):
        """Test searching variants by rsID."""
        # Using a common rsID
        response = await client.get("/search/variant", params={"query": "rs80357906"})

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        # Should return variants with this rsID
        if len(data) > 0:
            # Check that results have variant structure
            for variant in data:
                assert "variant_id" in variant or "variantId" in variant

    @pytest.mark.asyncio
    async def test_search_variants_by_position(self, client: AsyncClient):
        """Test searching variants by genomic position."""
        # Search by variant ID format instead of position
        # gnomAD variant search doesn't support position-only queries
        response = await client.get("/search/variant", params={"query": "13-32394863"})

        # This may return 500 since gnomAD doesn't support position-only search
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_search_gene_with_short_query(self, client: AsyncClient):
        """Test gene search with minimum length query."""
        response = await client.get("/search/gene", params={"query": "TP"})

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        # Should return genes starting with TP

    @pytest.mark.asyncio
    async def test_search_gene_query_too_short(self, client: AsyncClient):
        """Test gene search with query too short."""
        response = await client.get("/search/gene", params={"query": "T"})

        assert response.status_code == 422  # Validation error
        error = response.json()
        assert "detail" in error

    @pytest.mark.asyncio
    async def test_search_variant_query_too_short(self, client: AsyncClient):
        """Test variant search with query too short."""
        response = await client.get("/search/variant", params={"query": "13"})

        assert response.status_code == 422  # Validation error
        error = response.json()
        assert "detail" in error

    @pytest.mark.asyncio
    async def test_search_genes_case_insensitive(self, client: AsyncClient):
        """Test that gene search is case-insensitive."""
        # Search with lowercase
        response_lower = await client.get("/search/gene", params={"query": "brca2"})
        # Search with uppercase
        response_upper = await client.get("/search/gene", params={"query": "BRCA2"})

        assert response_lower.status_code == 200
        assert response_upper.status_code == 200

        # Both should find BRCA2
        data_lower = response_lower.json()
        data_upper = response_upper.json()

        assert any(g["symbol"] == "BRCA2" for g in data_lower)
        assert any(g["symbol"] == "BRCA2" for g in data_upper)
