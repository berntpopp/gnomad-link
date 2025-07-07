"""Shared dependencies for FastAPI routes."""

from typing import Optional
from gnomad_mcp.services import UnifiedFrequencyService
from gnomad_mcp.api import UnifiedGnomadClient

# Global service instance
_service: Optional[UnifiedFrequencyService] = None


def set_service(service: UnifiedFrequencyService):
    """Set the global service instance."""
    global _service
    _service = service


def get_service() -> UnifiedFrequencyService:
    """Get the global service instance."""
    if _service is None:
        raise RuntimeError(
            "Service not initialized. Server may not have started properly."
        )
    return _service
