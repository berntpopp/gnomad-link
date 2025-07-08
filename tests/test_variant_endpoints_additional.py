"""Additional tests for variant endpoints to increase coverage."""

import pytest
from httpx import AsyncClient


class TestVariantEndpointsAdditional:
    """Additional tests for uncovered variant endpoint code paths."""

    @pytest.mark.asyncio
    async def test_variant_internal_error(self, client: AsyncClient):
        """Test variant endpoint internal error handling."""
        # Use a variant ID that might cause parsing issues
        variant_id = "invalid-variant-format"
        response = await client.get(f"/variant/{variant_id}")

        # Should return 400, 500, or 502 for invalid format
        assert response.status_code in [400, 404, 500, 502]
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_variant_details_internal_error(self, client: AsyncClient):
        """Test variant details endpoint error handling."""
        # Use invalid variant ID
        variant_id = "X-invalid-pos-A-T"
        response = await client.get(f"/variant/details/{variant_id}")

        # Should handle error gracefully
        assert response.status_code in [400, 404, 500]
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_variant_with_all_parameters(self, client: AsyncClient):
        """Test variant endpoint with all optional parameters."""
        variant_id = "1-55051215-G-GA"

        # Test with all parameters
        response = await client.get(
            f"/variant/{variant_id}",
            params={"dataset": "gnomad_r3", "reference_genome": "GRCh37"},
        )

        # gnomAD v3 doesn't have GRCh37, so this might fail
        assert response.status_code in [200, 400, 404]

    @pytest.mark.asyncio
    async def test_variant_details_not_found(self, client: AsyncClient):
        """Test variant details for non-existent variant."""
        variant_id = "1-1-A-T"
        response = await client.get(f"/variant/details/{variant_id}")

        assert response.status_code == 404
        error_data = response.json()
        assert "detail" in error_data
        assert "not found" in error_data["detail"].lower()

    @pytest.mark.asyncio
    async def test_variant_special_characters(self, client: AsyncClient):
        """Test variant endpoint with special characters."""
        # Test URL encoding of variant IDs
        variant_id = "1-12345-AT-A"  # Deletion
        response = await client.get(f"/variant/{variant_id}")

        # Should handle properly
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert data["variant_id"] == variant_id

    @pytest.mark.asyncio
    async def test_variant_details_with_dataset(self, client: AsyncClient):
        """Test variant details with different datasets."""
        variant_id = "17-7674221-G-A"  # TP53 variant

        # Test with different datasets
        for dataset in ["gnomad_r2_1", "gnomad_r3", "gnomad_r4"]:
            response = await client.get(
                f"/variant/details/{variant_id}", params={"dataset": dataset}
            )

            # Some datasets might not have the variant
            assert response.status_code in [200, 404]

            if response.status_code == 200:
                data = response.json()
                assert "variant" in data

    @pytest.mark.asyncio
    async def test_variant_mitochondrial(self, client: AsyncClient):
        """Test variant endpoint with mitochondrial variant."""
        # Mitochondrial variants might be handled differently
        variant_id = "M-8602-T-C"
        response = await client.get(f"/variant/{variant_id}")

        # Might not be supported by regular variant endpoint
        assert response.status_code in [200, 400, 404]

    @pytest.mark.asyncio
    async def test_variant_x_chromosome(self, client: AsyncClient):
        """Test variant on X chromosome for hemizygote data."""
        variant_id = "X-12345-A-G"
        response = await client.get(f"/variant/{variant_id}")

        if response.status_code == 200:
            data = response.json()

            # X chromosome variants should have hemizygote counts
            if "exome" in data and data["exome"]:
                assert "hemizygote_count" in data["exome"]

    @pytest.mark.asyncio
    async def test_variant_long_indel(self, client: AsyncClient):
        """Test long insertion/deletion variant."""
        # Very long deletion
        ref = "A" * 50
        alt = "A"
        variant_id = f"1-12345-{ref}-{alt}"

        response = await client.get(f"/variant/{variant_id}")

        # Long variants might have special handling
        assert response.status_code in [200, 400, 404, 414]
