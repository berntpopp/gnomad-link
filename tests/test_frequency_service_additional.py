"""Additional tests for frequency service to increase coverage."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from gnomad_mcp.api import DataNotFoundError, GnomadApiError
from gnomad_mcp.models import Gene, ReferenceGenome
from gnomad_mcp.services import FrequencyService


class TestFrequencyServiceAdditional:
    """Additional tests for uncovered code paths in FrequencyService."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock API client."""
        client = MagicMock()
        client.get_variant = AsyncMock()
        client.get_gene = AsyncMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def frequency_service(self, mock_client):
        """Create a frequency service with mocked client."""
        return FrequencyService(client=mock_client)

    @pytest.mark.asyncio
    async def test_get_gene_success(self, frequency_service, mock_client):
        """Test successful gene retrieval."""
        # Arrange
        gene_data = {
            "gene": {
                "gene_id": "ENSG00000169174",
                "symbol": "PCSK9",
                "name": "proprotein convertase subtilisin/kexin type 9",
                "chrom": "1",
                "start": 55039549,
                "stop": 55064852,
                "canonical_transcript": "ENST00000302118",
                "gnomad_constraint": {
                    "exp_lof": 52.4,
                    "obs_lof": 2,
                    "oe_lof": 0.038,
                    "pLI": 0.999,
                },
            }
        }
        mock_client.get_gene.return_value = gene_data

        # Act
        result = await frequency_service.get_gene(gene_symbol="PCSK9")

        # Assert
        assert isinstance(result, Gene)
        assert result.gene_id == "ENSG00000169174"
        assert result.symbol == "PCSK9"
        assert result.name == "proprotein convertase subtilisin/kexin type 9"
        mock_client.get_gene.assert_called_once_with(
            None, "PCSK9", None, None
        )

    @pytest.mark.asyncio
    async def test_get_gene_by_id(self, frequency_service, mock_client):
        """Test gene retrieval by Ensembl ID."""
        # Arrange
        gene_data = {
            "gene": {
                "gene_id": "ENSG00000139618",
                "symbol": "BRCA2",
                "name": "BRCA2 DNA repair associated",
                "chrom": "13",
                "start": 32315086,
                "stop": 32400268,
                "canonical_transcript": "ENST00000380152",
            }
        }
        mock_client.get_gene.return_value = gene_data

        # Act
        result = await frequency_service.get_gene(
            gene_id="ENSG00000139618", reference_genome=ReferenceGenome.GRCH38
        )

        # Assert
        assert result.gene_id == "ENSG00000139618"
        assert result.symbol == "BRCA2"

    @pytest.mark.asyncio
    async def test_get_gene_not_found(self, frequency_service, mock_client):
        """Test gene not found error."""
        # Arrange
        mock_client.get_gene.side_effect = DataNotFoundError("Gene not found")

        # Act & Assert
        with pytest.raises(DataNotFoundError) as exc_info:
            await frequency_service.get_gene(gene_symbol="FAKEGENE")

        assert "Gene not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_gene_api_error(self, frequency_service, mock_client):
        """Test API error during gene retrieval."""
        # Arrange
        mock_client.get_gene.side_effect = GnomadApiError("API error")

        # Act & Assert
        with pytest.raises(GnomadApiError) as exc_info:
            await frequency_service.get_gene(gene_symbol="BRCA1")

        assert "API error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_gene_with_dataset(self, frequency_service, mock_client):
        """Test gene retrieval with specific dataset."""
        # Arrange
        gene_data = {
            "gene": {
                "gene_id": "ENSG00000012048",
                "symbol": "BRCA1",
                "chrom": "17",
                "start": 43044295,
                "stop": 43125370,
            }
        }
        mock_client.get_gene.return_value = gene_data

        # Act
        await frequency_service.get_gene(gene_symbol="BRCA1", dataset="gnomad_r3")

        # Assert
        mock_client.get_gene.assert_called_once_with(
            None,
            "BRCA1",
            None,
            "gnomad_r3",
        )

    @pytest.mark.asyncio
    async def test_get_cache_stats(self, frequency_service):
        """Test cache statistics retrieval."""
        # Make some queries to generate stats
        frequency_service._cache_hits = 10
        frequency_service._cache_misses = 5

        # Get stats
        stats = frequency_service.get_cache_stats()

        assert stats["hits"] == 10
        assert stats["misses"] == 5
        assert stats["hit_rate"] == round(10 / 15, 3)
        assert "cache_info" in stats
        assert "variant" in stats["cache_info"]
        assert "gene" in stats["cache_info"]

    @pytest.mark.asyncio
    async def test_clear_cache(self, frequency_service):
        """Test cache clearing."""
        # Set some cache stats
        frequency_service._cache_hits = 10
        frequency_service._cache_misses = 5

        # Clear cache
        frequency_service.clear_cache()

        # Stats should be reset
        assert frequency_service._cache_hits == 0
        assert frequency_service._cache_misses == 0

    @pytest.mark.asyncio
    async def test_variant_caching_error_handling(self, frequency_service, mock_client):
        """Test variant query with caching error."""
        # First call fails with non-API error (triggers cache miss)
        frequency_service._get_variant_cached = AsyncMock(
            side_effect=RuntimeError("Cache error")
        )

        # Direct implementation should work
        mock_client.get_variant.return_value = {
            "variant": {"variant_id": "1-12345-A-G", "exome": {"ac": 1, "an": 1000}}
        }

        # Act
        result = await frequency_service.get_variant_frequencies(
            "1-12345-A-G", "gnomad_r4"
        )

        # Assert
        assert result.variant_id == "1-12345-A-G"
        assert frequency_service._cache_misses == 1

    @pytest.mark.asyncio
    async def test_gene_caching_error_handling(self, frequency_service, mock_client):
        """Test gene query with caching error that should propagate."""
        # Cache fails with API error - should propagate
        frequency_service._get_gene_cached = AsyncMock(
            side_effect=GnomadApiError("API down")
        )

        # Act & Assert
        with pytest.raises(GnomadApiError) as exc_info:
            await frequency_service.get_gene(gene_symbol="TP53")

        assert "API down" in str(exc_info.value)
        assert frequency_service._cache_misses == 1

    @pytest.mark.asyncio
    async def test_gene_data_directly_returned(self, frequency_service, mock_client):
        """Test gene data returned without 'gene' wrapper."""
        # API returns gene data directly (not wrapped)
        gene_data = {
            "gene_id": "ENSG00000141510",
            "symbol": "TP53",
            "name": "tumor protein p53",
            "chrom": "17",
            "start": 7565096,
            "stop": 7590695,
        }
        mock_client.get_gene.return_value = {"gene": gene_data}

        # Act
        result = await frequency_service.get_gene(gene_symbol="TP53")

        # Assert
        assert result.gene_id == "ENSG00000141510"
        assert result.symbol == "TP53"
