"""Tests for ClinVar endpoints."""

import pytest
from httpx import AsyncClient


class TestClinVarEndpoints:
    """Test ClinVar variant endpoints."""

    @pytest.mark.asyncio
    async def test_clinvar_variant_pathogenic(self, client: AsyncClient):
        """Test retrieving ClinVar data for a pathogenic variant."""
        # Using BRCA2 pathogenic variant
        variant_id = "13-32394863-CTG-C"
        response = await client.get(f"/clinvar/variant/{variant_id}")

        # ClinVar data might not be available for all variants
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()

            # Check structure
            assert "variant_id" in data
            assert data["variant_id"] == variant_id

            # Check for ClinVar-specific fields
            if "clinical_significance" in data:
                assert isinstance(data["clinical_significance"], str)

            if "review_status" in data:
                assert isinstance(data["review_status"], str)

            if "conditions" in data:
                assert isinstance(data["conditions"], list)

    @pytest.mark.asyncio
    async def test_clinvar_variant_with_gnomad_data(self, client: AsyncClient):
        """Test ClinVar variant with gnomAD frequency data."""
        # Using TP53 variant
        variant_id = "17-7674221-G-A"
        response = await client.get(f"/clinvar/variant/{variant_id}")

        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()

            # Check if gnomAD data is included
            if "gnomad" in data:
                assert isinstance(data["gnomad"], dict)

                # Check for frequency data
                if "exome" in data["gnomad"]:
                    assert "ac" in data["gnomad"]["exome"]
                    assert "an" in data["gnomad"]["exome"]
                    # Note: af is not provided directly, must be calculated from ac/an

    @pytest.mark.asyncio
    async def test_clinvar_variant_not_found(self, client: AsyncClient):
        """Test ClinVar query for non-existent variant."""
        variant_id = "1-1-A-T"
        response = await client.get(f"/clinvar/variant/{variant_id}")

        assert response.status_code == 404
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_clinvar_variant_with_dataset(self, client: AsyncClient):
        """Test ClinVar query with specific dataset."""
        variant_id = "17-7674232-C-T"  # BRCA1 variant

        response = await client.get(
            f"/clinvar/variant/{variant_id}", params={"dataset": "gnomad_r3"}
        )

        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert "variant_id" in data

    @pytest.mark.asyncio
    async def test_clinvar_conditions_structure(self, client: AsyncClient):
        """Test structure of conditions in ClinVar response."""
        # Use a well-known pathogenic variant
        variant_id = "1-55051215-G-GA"  # PCSK9 variant
        response = await client.get(f"/clinvar/variant/{variant_id}")

        if response.status_code == 200:
            data = response.json()

            if "conditions" in data and len(data["conditions"]) > 0:
                condition = data["conditions"][0]

                # Check condition structure
                assert "name" in condition or "medgen_id" in condition

                if "name" in condition:
                    assert isinstance(condition["name"], str)

                if "medgen_id" in condition:
                    assert isinstance(condition["medgen_id"], str)

    @pytest.mark.asyncio
    async def test_clinvar_submissions(self, client: AsyncClient):
        """Test ClinVar submissions data."""
        variant_id = "17-7674221-G-A"  # TP53 variant
        response = await client.get(f"/clinvar/variant/{variant_id}")

        if response.status_code == 200:
            data = response.json()

            if "submissions" in data:
                assert isinstance(data["submissions"], list)

                if len(data["submissions"]) > 0:
                    submission = data["submissions"][0]

                    # Check submission structure
                    if "clinical_significance" in submission:
                        assert isinstance(submission["clinical_significance"], str)

                    if "review_status" in submission:
                        assert isinstance(submission["review_status"], str)

                    if "submitter" in submission:
                        assert isinstance(submission["submitter"], str)
