"""Unit tests for the frequency service."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from gnomad_mcp.api import VariantNotFoundError
from gnomad_mcp.models import VariantFrequencyResponse
from gnomad_mcp.services import FrequencyService


@pytest.fixture
def mock_client():
    """Create a mock API client."""
    client = MagicMock()
    client.get_variant = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def frequency_service(mock_client):
    """Create a frequency service with mocked client."""
    return FrequencyService(client=mock_client)


@pytest.fixture
def sample_api_response():
    """Sample API response for testing."""
    return {
        "variant": {
            "variant_id": "1-55039447-G-T",
            "exome": {
                "populations": [
                    {"id": "afr", "ac": 2, "an": 15300, "homozygote_count": 0},
                    {"id": "eas", "ac": 0, "an": 19950, "homozygote_count": 0},
                    {"id": "nfe", "ac": 5, "an": 113730, "homozygote_count": 1},
                ]
            },
            "genome": {
                "populations": [
                    {"id": "afr", "ac": 1, "an": 20744, "homozygote_count": 0},
                    {"id": "amr", "ac": 0, "an": 13648, "homozygote_count": 0},
                ]
            },
        }
    }


class TestFrequencyService:
    """Test cases for FrequencyService."""

    async def test_get_variant_frequencies_success(
        self, frequency_service, mock_client, sample_api_response
    ):
        """Test successful variant frequency retrieval."""
        # Arrange
        mock_client.get_variant.return_value = sample_api_response

        # Act
        result = await frequency_service.get_variant_frequencies(
            "1-55039447-G-T", "gnomad_r4"
        )

        # Assert
        assert isinstance(result, VariantFrequencyResponse)
        assert result.variant_id == "1-55039447-G-T"
        assert result.dataset == "gnomad_r4"

        # Check exome data
        assert result.exome is not None
        assert len(result.exome.populations) == 3
        assert result.exome.populations[0].name == "afr"
        assert result.exome.populations[0].allele_count == 2
        assert result.exome.populations[0].allele_number == 15300

        # Check genome data
        assert result.genome is not None
        assert len(result.genome.populations) == 2

        # Check calculated properties
        assert result.exome.total_allele_count == 7  # 2 + 0 + 5
        assert result.exome.overall_frequency == pytest.approx(
            7 / (15300 + 19950 + 113730)
        )

    async def test_get_variant_frequencies_not_found(
        self, frequency_service, mock_client
    ):
        """Test handling of variant not found."""
        # Arrange
        mock_client.get_variant.return_value = {"variant": None}

        # Act & Assert
        with pytest.raises(VariantNotFoundError) as exc_info:
            await frequency_service.get_variant_frequencies(
                "1-99999999-A-T", "gnomad_r4"
            )

        assert "not found" in str(exc_info.value)

    async def test_get_variant_frequencies_invalid_input(self, frequency_service):
        """Test validation of input parameters."""
        # Test empty variant_id
        with pytest.raises(ValueError) as exc_info:
            await frequency_service.get_variant_frequencies("", "gnomad_r4")
        assert "variant_id cannot be empty" in str(exc_info.value)

        # Test empty dataset
        with pytest.raises(ValueError) as exc_info:
            await frequency_service.get_variant_frequencies("1-12345-A-T", "")
        assert "dataset cannot be empty" in str(exc_info.value)

    async def test_get_variant_frequencies_no_population_data(
        self, frequency_service, mock_client
    ):
        """Test handling of variant with no population data."""
        # Arrange
        mock_client.get_variant.return_value = {
            "variant": {
                "variant_id": "1-55039447-G-T",
                "exome": {"populations": []},
                "genome": None,
            }
        }

        # Act
        result = await frequency_service.get_variant_frequencies(
            "1-55039447-G-T", "gnomad_r4"
        )

        # Assert
        assert result.variant_id == "1-55039447-G-T"
        assert result.exome is not None
        assert len(result.exome.populations) == 0
        assert result.genome is None
        assert not result.has_data  # No meaningful data

    async def test_process_populations_filters_empty(self, frequency_service):
        """Test that populations with no data are filtered out."""
        # Arrange
        raw_populations = [
            {"id": "afr", "ac": 5, "an": 1000, "homozygote_count": 0},
            {"id": "", "ac": 0, "an": 0, "homozygote_count": 0},  # Empty ID
            {"id": "eas", "ac": 0, "an": 0, "homozygote_count": 0},  # No alleles
            {"id": "nfe", "ac": 10, "an": 2000, "homozygote_count": 1},
        ]

        # Act
        processed = frequency_service._process_populations(raw_populations)

        # Assert
        assert len(processed) == 2  # Only afr and nfe should remain
        assert processed[0].name == "afr"
        assert processed[1].name == "nfe"

    async def test_service_cleanup(self, frequency_service, mock_client):
        """Test that service properly cleans up resources."""
        # Act
        await frequency_service.close()

        # Assert
        mock_client.close.assert_called_once()


class TestPopulationFrequencyModel:
    """Test cases for PopulationFrequency model."""

    def test_allele_frequency_calculation(self):
        """Test allele frequency calculation."""
        from gnomad_mcp.models import PopulationFrequency

        # Normal case
        pop = PopulationFrequency(
            name="test", allele_count=10, allele_number=1000, homozygote_count=0
        )
        assert pop.allele_frequency == pytest.approx(0.01)

        # Zero allele number
        pop_zero = PopulationFrequency(
            name="test", allele_count=10, allele_number=0, homozygote_count=0
        )
        assert pop_zero.allele_frequency is None
