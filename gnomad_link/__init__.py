"""gnomAD MCP Server - Unified server for gnomAD data access."""

__version__ = "6.0.0"
__author__ = "gnomAD MCP Team"

from .api import DataNotFoundError, GnomadApiError, UnifiedGnomadClient

# Import order matters to avoid circular imports
from .models import (
    ClinVarVariant,
    Gene,
    GeneSearchResult,
    PopulationFrequency,
    VariantDataSource,
    VariantFrequencyResponse,
)
from .services import FrequencyService

__all__ = [
    # Models
    "PopulationFrequency",
    "VariantDataSource",
    "VariantFrequencyResponse",
    "Gene",
    "GeneSearchResult",
    "ClinVarVariant",
    # API clients
    "UnifiedGnomadClient",
    # Services
    "FrequencyService",
    # Exceptions
    "GnomadApiError",
    "DataNotFoundError",
]
