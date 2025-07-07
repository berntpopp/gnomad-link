"""gnomAD MCP Server - Dual-interface server for gnomAD variant data."""

__version__ = "2.0.0"
__author__ = "gnomAD MCP Team"

# Import order matters to avoid circular imports
from .models import (
    PopulationFrequency,
    VariantDataSource,
    VariantFrequencyResponse,
)
from .api import GnomadApiClient

__all__ = [
    "PopulationFrequency",
    "VariantDataSource",
    "VariantFrequencyResponse",
    "GnomadApiClient",
]
