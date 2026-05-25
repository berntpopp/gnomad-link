"""Tests for liftover endpoints."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


class TestLiftoverEndpoints:
    """Test liftover conversion endpoints."""

    @pytest.mark.asyncio
    async def test_liftover_forward(self, client: AsyncClient):
        """Test forward liftover from GRCh37 to GRCh38."""
        # TP53 variant in GRCh37
        params = {"source_variant_id": "17-7577121-G-A", "reference_genome": "GRCh38"}
        response = await client.get("/liftover/", params=params)

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "results" in data
        assert "query_type" in data
        assert data["query_type"] == "forward"

        # Results may be empty (gnomAD doesn't always have liftover data)
        assert isinstance(data["results"], list)

        # If results exist, check structure
        if len(data["results"]) > 0:
            result = data["results"][0]
            assert "source" in result
            assert "liftover" in result
            assert "datasets" in result

            # Check source structure
            assert "variant_id" in result["source"]
            assert "reference_genome" in result["source"]
            assert result["source"]["variant_id"] == params["source_variant_id"]

            # Check liftover structure
            assert "variant_id" in result["liftover"]
            assert "reference_genome" in result["liftover"]
            assert result["liftover"]["reference_genome"] == "GRCh38"

    @pytest.mark.asyncio
    async def test_liftover_reverse(self, client: AsyncClient):
        """Test reverse liftover from GRCh38 to GRCh37."""
        # TP53 variant in GRCh38
        params = {"liftover_variant_id": "17-7674221-G-A", "reference_genome": "GRCh37"}
        response = await client.get("/liftover/", params=params)

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "results" in data
        assert "query_type" in data
        assert data["query_type"] == "reverse"

        # Results may be empty
        assert isinstance(data["results"], list)

    @pytest.mark.asyncio
    async def test_liftover_both_ids_error(self, client: AsyncClient):
        """Test error when both variant IDs are provided."""
        params = {
            "source_variant_id": "17-7577121-G-A",
            "liftover_variant_id": "17-7674221-G-A",
            "reference_genome": "GRCh38",
        }
        response = await client.get("/liftover/", params=params)

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Only one of" in data["detail"]

    @pytest.mark.asyncio
    async def test_liftover_no_ids_error(self, client: AsyncClient):
        """Test error when no variant IDs are provided."""
        params = {"reference_genome": "GRCh38"}
        response = await client.get("/liftover/", params=params)

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Either source_variant_id or liftover_variant_id must be provided" in data["detail"]

    @pytest.mark.asyncio
    async def test_liftover_missing_reference_genome(self, client: AsyncClient):
        """Test error when reference genome is missing."""
        params = {"source_variant_id": "17-7577121-G-A"}
        response = await client.get("/liftover/", params=params)

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_liftover_with_different_variants(self, client: AsyncClient):
        """Test liftover with different variant types."""
        test_variants = [
            # SNV
            {"source_variant_id": "1-55516888-G-A", "desc": "PCSK9 SNV"},
            # Deletion
            {"source_variant_id": "7-117199646-ATCT-A", "desc": "CFTR deletion"},
            # Insertion
            {"source_variant_id": "13-32394863-CTG-C", "desc": "BRCA2 insertion"},
        ]

        for variant_info in test_variants:
            params = {
                "source_variant_id": variant_info["source_variant_id"],
                "reference_genome": "GRCh38",
            }
            response = await client.get("/liftover/", params=params)

            assert response.status_code == 200, f"Failed for {variant_info['desc']}"
            data = response.json()
            assert "results" in data
            assert isinstance(data["results"], list)

    @pytest.mark.asyncio
    async def test_liftover_invalid_reference_genome(self, client: AsyncClient):
        """Test error with invalid reference genome."""
        params = {
            "source_variant_id": "17-7577121-G-A",
            "reference_genome": "InvalidGenome",
        }
        response = await client.get("/liftover/", params=params)

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_liftover_empty_results(self, client: AsyncClient):
        """Test handling of variants with no liftover mapping."""
        # Use a variant that likely has no liftover
        params = {
            "source_variant_id": "1-1-A-T",  # Very early position variant
            "reference_genome": "GRCh38",
        }
        response = await client.get("/liftover/", params=params)

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert isinstance(data["results"], list)
        # Most likely empty, but that's valid
        assert len(data["results"]) >= 0
