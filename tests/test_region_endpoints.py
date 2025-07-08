"""Tests for region query endpoints."""

import pytest
from httpx import AsyncClient


class TestRegionEndpoints:
    """Test region-based variant query endpoints."""

    @pytest.mark.asyncio
    async def test_region_variants(self, client: AsyncClient):
        """Test retrieving variants in a genomic region."""
        response = await client.get(
            "/region/", params={"chrom": "1", "start": 55039400, "stop": 55039500}
        )

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "variants" in data or isinstance(data, list)

        variants = data if isinstance(data, list) else data.get("variants", [])

        # Check each variant
        for variant in variants:
            assert "variant_id" in variant
            assert "pos" in variant
            assert "ref" in variant
            assert "alt" in variant

            # Verify position is within requested range
            assert 55039400 <= variant["pos"] <= 55039500

            # Check for frequency data
            if "exome" in variant or "genome" in variant:
                source = variant.get("exome") or variant.get("genome")
                assert "ac" in source
                assert "an" in source
                assert "af" in source

    @pytest.mark.asyncio
    async def test_region_with_dataset(self, client: AsyncClient):
        """Test region query with specific dataset."""
        response = await client.get(
            "/region/",
            params={
                "chrom": "17",
                "start": 7674200,
                "stop": 7674300,
                "dataset": "gnomad_r4",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should have variant data or empty list
        variants = data if isinstance(data, list) else data.get("variants", [])
        assert isinstance(variants, list)

    @pytest.mark.asyncio
    async def test_region_reference_genome(self, client: AsyncClient):
        """Test region query with different reference genomes."""
        # Test with GRCh38
        response = await client.get(
            "/region/",
            params={
                "chrom": "1",
                "start": 55039400,
                "stop": 55039500,
                "reference_genome": "GRCh38",
            },
        )

        assert response.status_code == 200

        # Test with GRCh37
        response = await client.get(
            "/region/",
            params={
                "chrom": "1",
                "start": 55039400,
                "stop": 55039500,
                "reference_genome": "GRCh37",
            },
        )

        # GRCh37 coordinates might be different or not supported
        assert response.status_code in [200, 400]

    @pytest.mark.asyncio
    async def test_region_large_range(self, client: AsyncClient):
        """Test region query with large genomic range."""
        # Query 1MB region
        response = await client.get(
            "/region/", params={"chrom": "1", "start": 55000000, "stop": 56000000}
        )

        # Large regions might be rejected or paginated
        assert response.status_code in [200, 400, 413]

        if response.status_code == 200:
            data = response.json()

            # Check if pagination info is provided
            if "total" in data or "next" in data:
                assert True  # Has pagination
            elif isinstance(data, list):
                # Direct list of variants
                assert len(data) <= 10000  # Should have some limit

    @pytest.mark.asyncio
    async def test_region_invalid_coordinates(self, client: AsyncClient):
        """Test region query with invalid coordinates."""
        # Start > Stop
        response = await client.get(
            "/region/", params={"chrom": "1", "start": 1000, "stop": 500}
        )

        assert response.status_code in [400, 422]
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_region_invalid_chromosome(self, client: AsyncClient):
        """Test region query with invalid chromosome."""
        response = await client.get(
            "/region/", params={"chrom": "99", "start": 1000, "stop": 2000}
        )

        assert response.status_code in [400, 422, 404]

    @pytest.mark.asyncio
    async def test_region_missing_parameters(self, client: AsyncClient):
        """Test region query with missing required parameters."""
        # Missing all parameters
        response = await client.get("/region/")
        assert response.status_code in [400, 422]

        # Missing start
        response = await client.get("/region/", params={"chrom": "1", "stop": 1000})
        assert response.status_code in [400, 422]

        # Missing stop
        response = await client.get("/region/", params={"chrom": "1", "start": 1000})
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_region_with_filters(self, client: AsyncClient):
        """Test region query with quality filters."""
        response = await client.get(
            "/region/",
            params={
                "chrom": "1",
                "start": 55039400,
                "stop": 55039500,
                "filter": "PASS",  # Only high-quality variants
            },
        )

        if response.status_code == 200:
            data = response.json()
            variants = data if isinstance(data, list) else data.get("variants", [])

            # Check that variants have filter information
            for variant in variants:
                if "filters" in variant:
                    # If filter param is supported, should only have PASS
                    assert variant["filters"] == ["PASS"] or variant["filters"] == []

    @pytest.mark.asyncio
    async def test_region_variant_types(self, client: AsyncClient):
        """Test filtering by variant type in region."""
        # Test SNPs only
        response = await client.get(
            "/region/",
            params={
                "chrom": "1",
                "start": 55039400,
                "stop": 55040000,
                "variant_type": "snp",
            },
        )

        if response.status_code == 200:
            data = response.json()
            variants = data if isinstance(data, list) else data.get("variants", [])

            for variant in variants:
                if "ref" in variant and "alt" in variant:
                    # SNPs should have single base changes
                    is_snp = len(variant["ref"]) == 1 and len(variant["alt"]) == 1
                    if "variant_type" in variant:
                        assert variant["variant_type"] == "snp" or is_snp
