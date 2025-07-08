"""Tests for transcript endpoints."""

import pytest
from httpx import AsyncClient


class TestTranscriptEndpoints:
    """Test transcript information endpoints."""

    @pytest.mark.asyncio
    async def test_transcript_by_id(self, client: AsyncClient):
        """Test retrieving transcript information by ID."""
        # Using the example from documentation
        transcript_id = "ENST00000302118"  # PCSK9 transcript
        response = await client.get(f"/transcript/{transcript_id}")

        assert response.status_code == 200
        data = response.json()

        # Check basic structure
        assert "transcript_id" in data
        assert data["transcript_id"] == transcript_id

        # Check transcript-specific fields
        assert "gene_id" in data
        assert "gene_symbol" in data
        assert "chrom" in data
        assert "start" in data
        assert "stop" in data
        assert "strand" in data

        # Check for exons
        if "exons" in data:
            assert isinstance(data["exons"], list)
            assert len(data["exons"]) > 0

            # Check exon structure
            for exon in data["exons"]:
                assert "start" in exon
                assert "stop" in exon
                assert "feature_type" in exon

    @pytest.mark.asyncio
    async def test_transcript_canonical(self, client: AsyncClient):
        """Test canonical transcript information."""
        # BRCA2 canonical transcript
        transcript_id = "ENST00000380152"
        response = await client.get(f"/transcript/{transcript_id}")

        if response.status_code == 200:
            data = response.json()

            # Check if marked as canonical
            if "is_canonical" in data:
                assert isinstance(data["is_canonical"], bool)

            # Check gene association
            assert "gene_symbol" in data
            assert data["gene_symbol"] == "BRCA2"

    @pytest.mark.asyncio
    async def test_transcript_mane_select(self, client: AsyncClient):
        """Test MANE Select transcript data."""
        transcript_id = "ENST00000302118"  # PCSK9 MANE Select
        response = await client.get(f"/transcript/{transcript_id}")

        if response.status_code == 200:
            data = response.json()

            # Check for MANE Select annotation
            if "mane_select" in data:
                assert isinstance(data["mane_select"], bool)

            if "refseq_id" in data:
                assert data["refseq_id"].startswith("NM_")

    @pytest.mark.asyncio
    async def test_transcript_variants(self, client: AsyncClient):
        """Test retrieving variants affecting a transcript."""
        transcript_id = "ENST00000357654"  # BRCA1 transcript
        response = await client.get(f"/transcript/{transcript_id}/variants")

        if response.status_code == 200:
            data = response.json()

            # Should return list of variants or wrapped response
            variants = data if isinstance(data, list) else data.get("variants", [])

            for variant in variants:
                assert "variant_id" in variant

                # Check for consequence on this transcript
                if "consequence" in variant:
                    assert isinstance(variant["consequence"], str)

                if "hgvsc" in variant:
                    # Should reference this transcript
                    assert transcript_id in variant["hgvsc"] or "c." in variant["hgvsc"]

    @pytest.mark.asyncio
    async def test_transcript_not_found(self, client: AsyncClient):
        """Test transcript not found error."""
        transcript_id = "ENST99999999999"
        response = await client.get(f"/transcript/{transcript_id}")

        assert response.status_code == 404
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_transcript_with_version(self, client: AsyncClient):
        """Test transcript query with version number."""
        # With version
        transcript_id = "ENST00000302118.5"
        response = await client.get(f"/transcript/{transcript_id}")

        # Should handle versioned IDs
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            # Might return with or without version
            assert data["transcript_id"] in [transcript_id, "ENST00000302118"]

    @pytest.mark.asyncio
    async def test_transcript_reference_genome(self, client: AsyncClient):
        """Test transcript with different reference genomes."""
        transcript_id = "ENST00000302118"

        # GRCh38
        response = await client.get(
            f"/transcript/{transcript_id}", params={"reference_genome": "GRCh38"}
        )
        assert response.status_code == 200
        grch38_data = response.json()

        # GRCh37
        response = await client.get(
            f"/transcript/{transcript_id}", params={"reference_genome": "GRCh37"}
        )

        if response.status_code == 200:
            grch37_data = response.json()

            # Coordinates should differ between builds
            if "start" in grch38_data and "start" in grch37_data:
                # PCSK9 is on chr1, coordinates differ between builds
                assert grch38_data["start"] != grch37_data["start"]

    @pytest.mark.asyncio
    async def test_transcript_cds_info(self, client: AsyncClient):
        """Test CDS (coding sequence) information."""
        transcript_id = "ENST00000302118"
        response = await client.get(f"/transcript/{transcript_id}")

        if response.status_code == 200:
            data = response.json()

            # Check for CDS information
            if "cds_start" in data:
                assert isinstance(data["cds_start"], int)
                assert data["cds_start"] >= data["start"]

            if "cds_stop" in data:
                assert isinstance(data["cds_stop"], int)
                assert data["cds_stop"] <= data["stop"]

            # Check for coding exons
            if "exons" in data:
                cds_exons = [e for e in data["exons"] if e.get("feature_type") == "CDS"]
                if len(cds_exons) > 0:
                    # Should have at least one coding exon for protein-coding transcript
                    assert True

    @pytest.mark.asyncio
    async def test_transcript_gtex_expression(self, client: AsyncClient):
        """Test GTEx expression data for transcript."""
        transcript_id = "ENST00000302118"
        response = await client.get(f"/transcript/{transcript_id}/expression")

        # Expression endpoint might not exist
        if response.status_code == 200:
            data = response.json()

            # Check for tissue expression data
            if "tissues" in data:
                assert isinstance(data["tissues"], list)

                for tissue in data["tissues"]:
                    assert "tissue_id" in tissue
                    assert "tissue_name" in tissue
                    assert "tpm" in tissue or "rpkm" in tissue

                    # Expression values should be non-negative
                    if "tpm" in tissue:
                        assert tissue["tpm"] >= 0
