"""Service layer for business logic."""

from .frequency_service_cached import CachedFrequencyService
from .unified_service import UnifiedFrequencyService

# Export the unified service as the default
FrequencyService = UnifiedFrequencyService

__all__ = [
    "FrequencyService",
    "UnifiedFrequencyService",
    "CachedFrequencyService",  # Keep for backward compatibility
]
