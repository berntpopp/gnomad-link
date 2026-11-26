"""API client module for gnomAD."""

from .base_client import (
    DataNotFoundError,
    GnomadApiError,
    RateLimitedError,
    UpstreamInputError,
    VariantNotFoundError,
    note_fetch,
    with_call_budget,
    with_fetch_times,
    without_waiting,
)
from .client import UnifiedGnomadClient

__all__ = [
    # Clients
    "UnifiedGnomadClient",
    # Exceptions
    "GnomadApiError",
    "VariantNotFoundError",
    "DataNotFoundError",
    "UpstreamInputError",
    "RateLimitedError",
    "note_fetch",
    "with_call_budget",
    "with_fetch_times",
    "without_waiting",
]
