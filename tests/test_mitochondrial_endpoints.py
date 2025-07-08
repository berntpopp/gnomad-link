"""Tests for mitochondrial variant endpoints."""

import pytest
from httpx import AsyncClient


class TestMitochondrialEndpoints:
    """Test mitochondrial variant endpoints."""

    @pytest.mark.asyncio
    async def test_mitochondrial_variant(self, client: AsyncClient):
        """Test retrieving mitochondrial variant data."""
        # Using the example from documentation
        variant_id = "M-8602-T-C"
        response = await client.get(f"/mitochondrial-variant/{variant_id}")

        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()

            # Check basic structure
            assert "variant_id" in data
            assert data["variant_id"] == variant_id

            # Mitochondrial-specific fields
            assert "pos" in data
            assert "ac_het" in data
            assert "ac_hom" in data

            # Check for haplogroup data
            if "haplogroups" in data:
                assert isinstance(data["haplogroups"], list)

                for haplogroup in data["haplogroups"]:
                    assert "id" in haplogroup
                    assert "ac_het" in haplogroup or "ac_hom" in haplogroup

                    if "faf" in haplogroup and haplogroup["faf"] is not None:
                        assert 0.0 <= haplogroup["faf"] <= 1.0

    @pytest.mark.asyncio
    async def test_mitochondrial_variant_heteroplasmy(self, client: AsyncClient):
        """Test heteroplasmy data for mitochondrial variants."""
        variant_id = "M-3243-A-G"  # Common pathogenic variant
        response = await client.get(f"/mitochondrial-variant/{variant_id}")

        if response.status_code == 200:
            data = response.json()

            # Check for heteroplasmy levels
            if "heteroplasmy" in data:
                assert isinstance(data["heteroplasmy"], dict)

                if "mean" in data["heteroplasmy"]:
                    assert 0.0 <= data["heteroplasmy"]["mean"] <= 1.0

                if "median" in data["heteroplasmy"]:
                    assert 0.0 <= data["heteroplasmy"]["median"] <= 1.0

    @pytest.mark.asyncio
    async def test_mitochondrial_variant_populations(self, client: AsyncClient):
        """Test population frequency for mitochondrial variants."""
        variant_id = "M-8602-T-C"
        response = await client.get(f"/mitochondrial-variant/{variant_id}")

        if response.status_code == 200:
            data = response.json()

            # Check for population data
            if "populations" in data:
                assert isinstance(data["populations"], list)

                for pop in data["populations"]:
                    assert "id" in pop
                    assert "ac_het" in pop or "ac_hom" in pop
                    assert "an" in pop

                    # Mitochondrial variants should have specific population IDs
                    # like 'afr', 'amr', 'asj', 'eas', 'fin', 'nfe', 'sas', 'oth'

    @pytest.mark.asyncio
    async def test_mitochondrial_variant_consequences(self, client: AsyncClient):
        """Test transcript consequences for mitochondrial variants."""
        variant_id = "M-1555-A-G"  # Known pathogenic variant
        response = await client.get(f"/mitochondrial-variant/{variant_id}")

        if response.status_code == 200:
            data = response.json()

            # Check for consequences
            if "transcript_consequences" in data:
                assert isinstance(data["transcript_consequences"], list)

                for consequence in data["transcript_consequences"]:
                    assert "gene_symbol" in consequence
                    assert (
                        "consequence" in consequence
                        or "consequence_terms" in consequence
                    )

                    # Mitochondrial genes have specific naming
                    if "gene_symbol" in consequence:
                        gene = consequence["gene_symbol"]
                        # MT genes often start with MT-
                        assert gene.startswith("MT-") or gene in ["MTRNR1", "MTRNR2"]

    @pytest.mark.asyncio
    async def test_mitochondrial_variant_clinical_significance(
        self, client: AsyncClient
    ):
        """Test clinical significance for mitochondrial variants."""
        # Known pathogenic variant
        variant_id = "M-3243-A-G"
        response = await client.get(f"/mitochondrial-variant/{variant_id}")

        if response.status_code == 200:
            data = response.json()

            # Check for clinical data
            if "clinical_significance" in data:
                assert isinstance(data["clinical_significance"], str)

                # Common values
                valid_significances = [
                    "pathogenic",
                    "likely_pathogenic",
                    "benign",
                    "likely_benign",
                    "uncertain_significance",
                ]

                significance = data["clinical_significance"].lower()
                assert any(vs in significance for vs in valid_significances)

    @pytest.mark.asyncio
    async def test_mitochondrial_variant_not_found(self, client: AsyncClient):
        """Test mitochondrial variant not found."""
        variant_id = "M-99999-A-T"
        response = await client.get(f"/mitochondrial-variant/{variant_id}")

        assert response.status_code == 404
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_mitochondrial_variant_invalid_format(self, client: AsyncClient):
        """Test invalid mitochondrial variant ID format."""
        # Missing M prefix
        variant_id = "8602-T-C"
        response = await client.get(f"/mitochondrial-variant/{variant_id}")

        # Should either 404 or 400 for bad format
        assert response.status_code in [400, 404]

    @pytest.mark.asyncio
    async def test_mitochondrial_variant_with_dataset(self, client: AsyncClient):
        """Test mitochondrial variant with specific dataset."""
        variant_id = "M-8602-T-C"

        # Try different datasets
        for dataset in ["gnomad_r3", "gnomad_r4"]:
            response = await client.get(
                f"/mitochondrial-variant/{variant_id}", params={"dataset": dataset}
            )

            if response.status_code == 200:
                data = response.json()
                assert "variant_id" in data

                # Dataset info might be included
                if "dataset" in data:
                    assert data["dataset"] == dataset
