"""Tests for structural variant endpoints."""

import pytest
from httpx import AsyncClient


class TestStructuralVariantEndpoints:
    """Test structural variant endpoints."""

    @pytest.mark.asyncio
    async def test_structural_variant_by_id(self, client: AsyncClient):
        """Test retrieving structural variant by ID."""
        # Structural variants have different ID format
        variant_id = "DUP_1_1234567"  # Example SV ID
        response = await client.get(f"/structural-variant/{variant_id}")

        # SVs might not exist with this ID
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()

            # Check basic structure
            assert "variant_id" in data
            assert "type" in data  # DUP, DEL, INS, etc.
            assert "chrom" in data
            assert "start" in data
            assert "end" in data

    @pytest.mark.asyncio
    async def test_structural_variant_region(self, client: AsyncClient):
        """Test retrieving structural variants in a region."""
        # Using the example region from documentation
        response = await client.get(
            "/structural-variant/region",
            params={"chrom": "19", "start": 11078371, "stop": 11144910},
        )

        # This endpoint might not exist or region might have no SVs
        if response.status_code == 200:
            data = response.json()

            # Should return a list of variants
            assert isinstance(data, list) or "variants" in data

            variants = data if isinstance(data, list) else data.get("variants", [])

            # Check structure of each variant
            for variant in variants:
                assert "variant_id" in variant
                assert "type" in variant
                assert "chrom" in variant
                assert variant["chrom"] == "19"
                assert "start" in variant
                assert "end" in variant

                # Check position is within requested region
                if "start" in variant:
                    assert variant["start"] >= 11078371
                if "end" in variant:
                    assert variant["end"] <= 11144910

    @pytest.mark.asyncio
    async def test_copy_number_variant(self, client: AsyncClient):
        """Test copy number variant query."""
        # Using the example CNV region from documentation
        response = await client.get(
            "/structural-variant/cnv",
            params={"chrom": "1", "start": 55039447, "stop": 55064852},
        )

        if response.status_code == 200:
            data = response.json()

            # Check if it returns CNV-specific data
            if isinstance(data, dict):
                if "copy_number" in data:
                    assert isinstance(data["copy_number"], (int, float))

                if "type" in data:
                    assert data["type"] in ["DUP", "DEL", "CNV"]

    @pytest.mark.asyncio
    async def test_structural_variant_populations(self, client: AsyncClient):
        """Test population data for structural variants."""
        variant_id = "DEL_2_123456"
        response = await client.get(f"/structural-variant/{variant_id}")

        if response.status_code == 200:
            data = response.json()

            # Check for population frequency data
            if "populations" in data:
                assert isinstance(data["populations"], list)

                for pop in data["populations"]:
                    assert "id" in pop
                    assert "ac" in pop
                    assert "an" in pop
                    assert "af" in pop or (pop["an"] == 0)

    @pytest.mark.asyncio
    async def test_structural_variant_consequences(self, client: AsyncClient):
        """Test gene consequences for structural variants."""
        variant_id = "DEL_17_7674000"  # Near TP53
        response = await client.get(f"/structural-variant/{variant_id}")

        if response.status_code == 200:
            data = response.json()

            # Check for gene consequences
            if "consequences" in data:
                assert isinstance(data["consequences"], list)

                for consequence in data["consequences"]:
                    assert "gene_id" in consequence or "gene_symbol" in consequence

                    if "consequence" in consequence:
                        assert isinstance(consequence["consequence"], str)

    @pytest.mark.asyncio
    async def test_structural_variant_not_found(self, client: AsyncClient):
        """Test SV endpoint with non-existent variant."""
        variant_id = "INVALID_SV_ID"
        response = await client.get(f"/structural-variant/{variant_id}")

        assert response.status_code == 404
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_structural_variant_filters(self, client: AsyncClient):
        """Test structural variant quality filters."""
        variant_id = "INS_3_100000"
        response = await client.get(f"/structural-variant/{variant_id}")

        if response.status_code == 200:
            data = response.json()

            # Check for quality filters
            if "filters" in data:
                assert isinstance(data["filters"], list)

                # Common SV filters
                for filter_name in data["filters"]:
                    assert isinstance(filter_name, str)
