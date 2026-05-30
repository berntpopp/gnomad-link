"""Pydantic models for gnomAD read-depth coverage (gene, region, variant)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CoverageBin(BaseModel):
    """A single per-position coverage bin (gene/region scope)."""

    pos: int
    mean: float | None = None
    median: float | None = None
    over_1: float | None = None
    over_5: float | None = None
    over_10: float | None = None
    over_15: float | None = None
    over_20: float | None = None
    over_25: float | None = None
    over_30: float | None = None
    over_50: float | None = None
    over_100: float | None = None

    model_config = ConfigDict(extra="allow")


class FeatureCoverage(BaseModel):
    """Coverage for a gene or region: per-position exome/genome bins."""

    exome: list[CoverageBin] = Field(default_factory=list)
    genome: list[CoverageBin] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class Coverage(BaseModel):
    """Scalar coverage for a single variant (no bins, no pos)."""

    mean: float | None = None
    median: float | None = None
    over_20: float | None = None
    over_30: float | None = None

    model_config = ConfigDict(extra="allow")
