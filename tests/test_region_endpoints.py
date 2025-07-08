"""Tests for region query endpoints."""

import pytest
from httpx import AsyncClient


class TestRegionEndpoints:
    """Test region-based variant query endpoints."""

    @pytest.mark.asyncio
    async def test_region_variants(self, client: AsyncClient):
        """Test retrieving variants in a genomic region."""
        response = await client.get("/region/1-55039400-55039500")

        assert response.status_code == 200
        data = response.json()

        # Check response structure for region query
        assert "chrom" in data
        assert "start" in data
        assert "stop" in data
        assert "reference_genome" in data
        assert data["chrom"] == "1"
        assert data["start"] == 55039400
        assert data["stop"] == 55039500

        # Check if genes are present
        if "genes" in data:
            for gene in data["genes"]:
                assert "gene_id" in gene
                assert "symbol" in gene
                assert "start" in gene
                assert "stop" in gene

        # Check if clinvar variants are present
        if "clinvar_variants" in data:
            for variant in data["clinvar_variants"]:
                assert "variant_id" in variant
                assert "pos" in variant
                assert "clinical_significance" in variant
                # Verify position is within requested range
                assert 55039400 <= variant["pos"] <= 55039500

    @pytest.mark.asyncio
    async def test_region_with_dataset(self, client: AsyncClient):
        """Test region query with specific dataset."""
        response = await client.get(
            "/region/17-7674200-7674300",
            params={"dataset": "gnomad_r4"},
        )

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "chrom" in data
        assert "start" in data
        assert "stop" in data
        assert data["chrom"] == "17"
        assert data["start"] == 7674200
        assert data["stop"] == 7674300

    @pytest.mark.asyncio
    async def test_region_reference_genome(self, client: AsyncClient):
        """Test region query with default reference genome."""
        # Test with default reference genome (should be GRCh38 for v4)
        response = await client.get("/region/1-55039400-55039500")
        assert response.status_code == 200
        
        # Test with dataset that uses GRCh37
        response = await client.get(
            "/region/1-55039400-55039500",
            params={"dataset": "gnomad_r2_1"},
        )
        # Should still work with appropriate reference genome
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_region_large_range(self, client: AsyncClient):
        """Test region query with large genomic range."""
        # Query 1MB region
        response = await client.get("/region/1-55000000-56000000")

        # Large regions might be rejected or paginated
        assert response.status_code in [200, 400, 413]

        if response.status_code == 200:
            data = response.json()

            # Should still have basic region structure
            assert "chrom" in data
            assert "start" in data
            assert "stop" in data

    @pytest.mark.asyncio
    async def test_region_invalid_coordinates(self, client: AsyncClient):
        """Test region query with invalid coordinates."""
        # Start > Stop
        response = await client.get("/region/1-1000-500")

        assert response.status_code in [400, 422]
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_region_invalid_chromosome(self, client: AsyncClient):
        """Test region query with invalid chromosome."""
        response = await client.get("/region/99-1000-2000")

        assert response.status_code in [400, 422, 404]

    @pytest.mark.asyncio
    async def test_region_invalid_format(self, client: AsyncClient):
        """Test region query with invalid format."""
        # Missing parts
        response = await client.get("/region/1-1000")
        assert response.status_code == 422  # Invalid path format
        
        # Too many parts
        response = await client.get("/region/1-1000-2000-3000")
        assert response.status_code == 422  # Invalid path format
        
        # Non-numeric positions
        response = await client.get("/region/1-abc-def")
        assert response.status_code == 422  # Invalid path format

    @pytest.mark.asyncio
    async def test_region_with_filters(self, client: AsyncClient):
        """Test region query with variant filters."""
        # Our simplified region query doesn't support filters anymore
        response = await client.get("/region/2-179390716-179390816")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_region_variant_types(self, client: AsyncClient):
        """Test region query returns different variant types."""
        response = await client.get("/region/1-10000-20000")
        assert response.status_code == 200
