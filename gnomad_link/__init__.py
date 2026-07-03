"""gnomAD MCP Server - Unified server for gnomAD data access."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("gnomad-link")
except PackageNotFoundError:  # pragma: no cover - source checkout without install
    __version__ = "0.0.0"

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
    # Version
    "__version__",
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
