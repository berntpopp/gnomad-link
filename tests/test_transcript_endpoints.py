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
        assert "gene" in data
        assert "symbol" in data["gene"]
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

            # Check if marked as canonical through gene data
            assert "gene" in data
            if "canonical_transcript_id" in data["gene"]:
                is_canonical = data["gene"]["canonical_transcript_id"] == transcript_id
                assert isinstance(is_canonical, bool)

            # Check gene association
            assert "symbol" in data["gene"]
            assert data["gene"]["symbol"] == "BRCA2"

    @pytest.mark.asyncio
    async def test_transcript_mane_select(self, client: AsyncClient):
        """Test MANE Select transcript data."""
        transcript_id = "ENST00000302118"  # PCSK9 MANE Select
        response = await client.get(f"/transcript/{transcript_id}")

        if response.status_code == 200:
            data = response.json()

            # Check for MANE Select status through gene data
            assert "gene" in data
            if "mane_select_transcript" in data["gene"]:
                mane = data["gene"]["mane_select_transcript"]
                if mane and mane.get("ensembl_id") == transcript_id:
                    # This is a MANE Select transcript
                    assert "refseq_id" in mane
                    assert mane["refseq_id"].startswith("NM_")

    # Transcript variants endpoint not yet implemented
    # @pytest.mark.asyncio
    # async def test_transcript_variants(self, client: AsyncClient):
    #     """Test retrieving variants in a transcript."""
    #     transcript_id = "ENST00000357654"  # BRCA1
    #     response = await client.get(f"/transcript/{transcript_id}/variants")
    #
    #     if response.status_code == 200:
    #         data = response.json()
    #         assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_transcript_not_found(self, client: AsyncClient):
        """Test transcript not found error."""
        transcript_id = "ENST99999999999"
        response = await client.get(f"/transcript/{transcript_id}")

        assert response.status_code == 404
        assert "detail" in response.json()

    @pytest.mark.asyncio
    async def test_transcript_with_version(self, client: AsyncClient):
        """Test transcript ID with version number."""
        # Transcript ID with version
        transcript_id = "ENST00000357654.9"
        response = await client.get(f"/transcript/{transcript_id}")

        # Should handle versioned IDs
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_transcript_reference_genome(self, client: AsyncClient):
        """Test transcript with different reference genomes."""
        transcript_id = "ENST00000357654"

        # Test GRCh38
        response = await client.get(
            f"/transcript/{transcript_id}",
            params={"reference_genome": "GRCh38"}
        )
        if response.status_code == 200:
            data = response.json()
            assert data["reference_genome"] == "GRCh38"

        # Test GRCh37
        response = await client.get(
            f"/transcript/{transcript_id}",
            params={"reference_genome": "GRCh37"}
        )
        if response.status_code == 200:
            data = response.json()
            assert data["reference_genome"] == "GRCh37"

    @pytest.mark.asyncio
    async def test_transcript_cds_info(self, client: AsyncClient):
        """Test CDS information in transcript."""
        transcript_id = "ENST00000357654"  # BRCA1
        response = await client.get(f"/transcript/{transcript_id}")

        if response.status_code == 200:
            data = response.json()

            # Check for CDS information in exons
            if "exons" in data:
                cds_exons = [e for e in data["exons"] if e.get("feature_type") == "CDS"]
                if cds_exons:
                    # CDS exons should have valid coordinates
                    for exon in cds_exons:
                        assert exon["start"] <= exon["stop"]

    # GTEx expression endpoint not yet implemented
    # @pytest.mark.asyncio
    # async def test_transcript_expression(self, client: AsyncClient):
    #     """Test GTEx expression data for transcript."""
    #     transcript_id = "ENST00000302118"  # PCSK9
    #     response = await client.get(f"/transcript/{transcript_id}/expression")
    #
    #     if response.status_code == 200:
    #         data = response.json()
    #         assert isinstance(data, dict)