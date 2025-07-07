"""gnomAD MCP Server - Unified server for gnomAD data access."""

__version__ = "4.0.0"
__author__ = "gnomAD MCP Team"

# Import order matters to avoid circular imports
from .models import (
    PopulationFrequency,
    VariantDataSource,
    VariantFrequencyResponse,
    Gene,
    GeneSearchResult,
    ClinVarVariant,
)
from .api import (
    UnifiedGnomadClient,
    GnomadApiClient,  # Backward compatibility
    GnomadApiError,
    DataNotFoundError,
)
from .services import (
    FrequencyService,
    UnifiedFrequencyService,
)

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
    "GnomadApiClient",  # Backward compatibility
    # Services
    "FrequencyService",
    "UnifiedFrequencyService",
    # Exceptions
    "GnomadApiError",
    "DataNotFoundError",
]
