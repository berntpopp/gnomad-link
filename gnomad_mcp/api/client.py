"""GraphQL client for interacting with the gnomAD API - backward compatibility wrapper."""

from typing import Dict, Any, Optional

from .client_v2 import GnomadApiClient as _GnomadApiClient
from .base_client import GnomadApiError, VariantNotFoundError

# Re-export for backward compatibility
GnomadApiClient = _GnomadApiClient

__all__ = ["GnomadApiClient", "GnomadApiError", "VariantNotFoundError"]
