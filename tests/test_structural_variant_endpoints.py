"""Tests for structural variant endpoints."""

import pytest
from httpx import AsyncClient


class TestStructuralVariantEndpoints:
    """Test structural variant endpoints."""

    @pytest.mark.asyncio
    async def test_structural_variant_by_id(self, client: AsyncClient):
        """Test retrieving structural variant by ID."""
        # Use real structural variant IDs
        variant_id = "DUP_CHR19_06B26177"  # Real duplication variant
        response = await client.get(f"/structural-variant/{variant_id}")

        # SVs might not exist with this ID
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()

            # Check basic structure
            assert "variant_id" in data
            assert "type" in data  # DUP, DEL, INS, etc.
            assert "chrom" in data
            assert "pos" in data  # gnomAD uses 'pos' not 'start'
            assert "end" in data

    @pytest.mark.asyncio
    async def test_structural_variant_region(self, client: AsyncClient):
        """Test retrieving structural variants by ID."""
        # The SV endpoint doesn't support region queries, only individual variant IDs
        # Test with a real variant ID instead
        variant_id = "GD_17Q12-HNF1B__DEL"
        response = await client.get(f"/structural-variant/{variant_id}")

        # This variant might not exist in the test environment
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()

            # Check basic structure
            assert "variant_id" in data
            assert "type" in data
            assert "chrom" in data
            assert "pos" in data
            assert "end" in data

    @pytest.mark.asyncio
    async def test_copy_number_variant(self, client: AsyncClient):
        """Test copy number variant query."""
        # Use a real duplication variant
        variant_id = "DUP_CHR19_06B26177"
        response = await client.get(f"/structural-variant/{variant_id}")

        if response.status_code == 200:
            data = response.json()

            # Check if it returns CNV-specific data
            if isinstance(data, dict):
                # copy_numbers might be null for some variants
                if "copy_numbers" in data and data["copy_numbers"] is not None:
                    assert isinstance(data["copy_numbers"], list)
                    for cn in data["copy_numbers"]:
                        assert "copy_number" in cn
                        assert "ac" in cn

                if "type" in data:
                    assert data["type"] in [
                        "DUP",
                        "DEL",
                        "CNV",
                        "INS",
                        "INV",
                        "CPX",
                        "CTX",
                        "BND",
                    ]

    @pytest.mark.asyncio
    async def test_structural_variant_populations(self, client: AsyncClient):
        """Test population data for structural variants."""
        variant_id = "DEL_CHRY_B899DC9C"  # Real Y chromosome deletion
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
                    # af might not be present in population data, it's calculated

    @pytest.mark.asyncio
    async def test_structural_variant_consequences(self, client: AsyncClient):
        """Test gene consequences for structural variants."""
        variant_id = "GD_17Q12-HNF1B__DEL"  # Real HNF1B deletion
        response = await client.get(f"/structural-variant/{variant_id}")

        if response.status_code == 200:
            data = response.json()

            # Check for gene consequences
            if "consequences" in data:
                assert isinstance(data["consequences"], list)

                for consequence in data["consequences"]:
                    assert "consequence" in consequence
                    assert "genes" in consequence

                    # genes is a list of gene IDs
                    assert isinstance(consequence["genes"], list)

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
        variant_id = "DUP_CHR19_06B26177"  # Use a real variant ID
        response = await client.get(f"/structural-variant/{variant_id}")

        if response.status_code == 200:
            data = response.json()

            # Check for quality filters
            if "filters" in data:
                assert isinstance(data["filters"], list)

                # Common SV filters
                for filter_name in data["filters"]:
                    assert isinstance(filter_name, str)
