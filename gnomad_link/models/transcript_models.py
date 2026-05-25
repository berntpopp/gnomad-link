"""Pydantic models for transcript queries."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TranscriptExon(BaseModel):
    feature_type: str
    start: int
    stop: int


class Transcript(BaseModel):
    transcript_id: str
    gene_id: str | None = None
    gene_symbol: str | None = None
    chrom: str
    start: int
    stop: int
    strand: str | None = None
    reference_genome: str
    exons: list[TranscriptExon] = Field(default_factory=list)
    gtex_tissue_expression: list[dict] | None = None

    model_config = ConfigDict(extra="allow")
