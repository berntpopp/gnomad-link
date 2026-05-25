"""Pydantic models for genomic region queries."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RegionGene(BaseModel):
    gene_id: str
    symbol: str
    start: int
    stop: int


class RegionClinVarVariant(BaseModel):
    variant_id: str
    clinical_significance: str | None = None
    gold_stars: int | None = None
    major_consequence: str | None = None
    pos: int
    review_status: str | None = None


class Region(BaseModel):
    chrom: str
    start: int
    stop: int
    reference_genome: str
    genes: list[RegionGene] = Field(default_factory=list)
    clinvar_variants: list[RegionClinVarVariant] = Field(default_factory=list)
    variants: list[dict] | None = None  # SNV/indel array; opaque until shaping covers it
    truncated: dict | None = Field(
        default=None, description="Set when filters or limits dropped rows"
    )

    model_config = ConfigDict(extra="allow")
