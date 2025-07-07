"""API client module for gnomAD."""

from .base_client import (
    GnomadApiError,
    VariantNotFoundError,
    DataNotFoundError,
)
from .client_v2 import GnomadApiClient  # Backward compatibility
from .unified_client import UnifiedGnomadClient

__all__ = [
    # Clients
    "GnomadApiClient",  # Backward compatibility
    "UnifiedGnomadClient",
    # Exceptions
    "GnomadApiError",
    "VariantNotFoundError",
    "DataNotFoundError",
]
