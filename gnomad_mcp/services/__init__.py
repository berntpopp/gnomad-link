"""Service layer for business logic."""

from .frequency_service_cached import CachedFrequencyService

# Export the cached version as the default FrequencyService
FrequencyService = CachedFrequencyService

__all__ = ["FrequencyService", "CachedFrequencyService"]
