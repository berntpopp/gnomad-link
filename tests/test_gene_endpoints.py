"""Tests for gene endpoints using cancer predisposition genes."""

import pytest
from httpx import AsyncClient


class TestGeneEndpoints:
    """Test gene endpoints with cancer gene examples."""

    @pytest.mark.asyncio
    async def test_brca2_gene_by_symbol(self, client: AsyncClient):
        """Test BRCA2 gene lookup by symbol."""
        response = await client.get("/gene/", params={"gene_symbol": "BRCA2"})

        assert response.status_code == 200
        data = response.json()

        # API returns these fields directly
        assert data["gene_id"] == "ENSG00000139618"
        assert "name" in data
        assert "BRCA2" in data["name"]
        assert data["chrom"] == "13"

        # Check constraint scores - they're under gnomad_constraint
        if "gnomad_constraint" in data:
            # pLI might be lowercase 'pli' in the API response
            assert (
                "pli" in data["gnomad_constraint"] or "pLI" in data["gnomad_constraint"]
            )
            assert "oe_lof" in data["gnomad_constraint"]

    @pytest.mark.asyncio
    async def test_brca1_gene_by_symbol(self, client: AsyncClient):
        """Test BRCA1 gene lookup by symbol."""
        response = await client.get("/gene/", params={"gene_symbol": "BRCA1"})

        assert response.status_code == 200
        data = response.json()

        assert data["gene_id"] == "ENSG00000012048"
        assert "name" in data
        assert "BRCA1" in data["name"]
        assert data["chrom"] == "17"

    @pytest.mark.asyncio
    async def test_tp53_gene_by_symbol(self, client: AsyncClient):
        """Test TP53 gene lookup by symbol."""
        response = await client.get("/gene/", params={"gene_symbol": "TP53"})

        assert response.status_code == 200
        data = response.json()

        assert data["gene_id"] == "ENSG00000141510"
        assert "name" in data
        assert "TP53" in data["name"] or "tumor protein" in data["name"].lower()
        assert data["chrom"] == "17"

        # TP53 should have high pLI score
        if "gnomad_constraint" in data and "pli" in data["gnomad_constraint"]:
            assert data["gnomad_constraint"]["pli"] > 0.9

    @pytest.mark.asyncio
    async def test_apc_gene_by_symbol(self, client: AsyncClient):
        """Test APC gene lookup by symbol."""
        response = await client.get("/gene/", params={"gene_symbol": "APC"})

        assert response.status_code == 200
        data = response.json()

        assert "name" in data
        assert "APC" in data["name"]
        assert data["chrom"] == "5"

    @pytest.mark.asyncio
    async def test_pcsk9_gene_by_symbol(self, client: AsyncClient):
        """Test PCSK9 gene lookup by symbol."""
        response = await client.get("/gene/", params={"gene_symbol": "PCSK9"})

        assert response.status_code == 200
        data = response.json()

        assert data["gene_id"] == "ENSG00000169174"
        assert "name" in data
        assert (
            "PCSK9" in data["name"] or "proprotein convertase" in data["name"].lower()
        )
        assert data["chrom"] == "1"

    @pytest.mark.asyncio
    async def test_gene_by_ensembl_id(self, client: AsyncClient):
        """Test gene lookup by Ensembl ID."""
        # Using BRCA2 Ensembl ID
        response = await client.get("/gene/", params={"gene_id": "ENSG00000139618"})

        assert response.status_code == 200
        data = response.json()

        assert data["gene_id"] == "ENSG00000139618"
        assert "name" in data
        assert "BRCA2" in data["name"]

    @pytest.mark.asyncio
    async def test_gene_with_reference_genome(self, client: AsyncClient):
        """Test gene lookup with specific reference genome."""
        response = await client.get(
            "/gene/", params={"gene_symbol": "BRCA1", "reference_genome": "GRCh37"}
        )

        assert response.status_code == 200
        data = response.json()

        assert "name" in data
        assert "BRCA1" in data["name"]
        # Reference genome is passed as parameter, not returned in response

    @pytest.mark.asyncio
    async def test_gene_not_found(self, client: AsyncClient):
        """Test gene not found error."""
        response = await client.get("/gene/", params={"gene_symbol": "FAKEGENE123"})

        assert response.status_code == 404
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_gene_missing_parameters(self, client: AsyncClient):
        """Test error when neither gene_id nor gene_symbol provided."""
        response = await client.get("/gene/")

        assert response.status_code == 400
        error = response.json()
        assert "detail" in error
        assert "gene_id" in error["detail"] or "gene_symbol" in error["detail"]

    @pytest.mark.asyncio
    async def test_gene_variants_endpoint(self, client: AsyncClient):
        """Test getting variants within a gene."""
        # Using TP53 gene ID
        gene_id = "ENSG00000141510"
        response = await client.get(f"/gene/variants/{gene_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["gene_id"] == gene_id
        assert "variant_count" in data
        assert "variants" in data
        assert isinstance(data["variants"], list)

        # TP53 should have many variants
        if data["variant_count"] > 0:
            variant = data["variants"][0]
            assert "variant_id" in variant
            assert "consequence" in variant or "annotation" in variant

    @pytest.mark.asyncio
    async def test_gene_transcripts_info(self, client: AsyncClient):
        """Test that gene info includes transcript information."""
        response = await client.get("/gene/", params={"gene_symbol": "BRCA2"})

        assert response.status_code == 200
        data = response.json()

        # Check for canonical transcript - field is named canonical_transcript
        if "canonical_transcript" in data:
            assert data["canonical_transcript"].startswith("ENST")

        # Check for transcripts array
        if "transcripts" in data:
            assert isinstance(data["transcripts"], list)
            if len(data["transcripts"]) > 0:
                assert "transcript_id" in data["transcripts"][0]
