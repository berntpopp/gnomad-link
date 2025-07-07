"""Data models for the gnomAD MCP server."""

from .variant_models import (
    PopulationFrequency,
    VariantDataSource,
    VariantFrequencyResponse,
)

__all__ = [
    "PopulationFrequency",
    "VariantDataSource",
    "VariantFrequencyResponse",
]
