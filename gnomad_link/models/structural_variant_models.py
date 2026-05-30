"""Data models for structural variant queries."""

from typing import Any

from pydantic import BaseModel, Field


class SVConsequence(BaseModel):
    """Consequence of a structural variant."""

    consequence: str = Field(..., description="Consequence type")
    genes: list[str] = Field(default_factory=list, description="Affected genes")


class SVCopyNumber(BaseModel):
    """Copy number information for a structural variant."""

    copy_number: int = Field(..., description="Copy number")
    ac: int = Field(..., description="Allele count")


class SVPopulation(BaseModel):
    """Population frequency data for a structural variant."""

    id: str = Field(..., description="Population identifier", alias="id")
    ac: int = Field(..., description="Allele count")
    an: int = Field(..., description="Allele number")
    homozygote_count: int | None = Field(None, description="Number of homozygotes")
    hemizygote_count: int | None = Field(None, description="Number of hemizygotes")


class StructuralVariant(BaseModel):
    """Structural variant information."""

    variant_id: str = Field(..., description="Variant identifier")
    reference_genome: str = Field(..., description="Reference genome")
    chrom: str = Field(..., description="Chromosome")
    chrom2: str | None = Field(None, description="Second chromosome (for translocations)")
    # pos/end/ac/an/af are null for some SV classes (BND/CTX translocations,
    # complex CPX), so they are genuinely optional despite always being present
    # for deletions/duplications.
    pos: int | None = Field(None, description="Start position")
    pos2: int | None = Field(None, description="Second position")
    end: int | None = Field(None, description="End position")
    end2: int | None = Field(None, description="Second end position")
    length: int | None = Field(None, description="Length of variant")
    type: str = Field(..., description="Type of structural variant")
    alts: list[str] | None = Field(None, description="Alternate alleles")
    algorithms: list[str] | None = Field(None, description="Detection algorithms")
    ac: int | None = Field(None, description="Total allele count")
    an: int | None = Field(None, description="Total allele number")
    af: float | None = Field(None, description="Allele frequency")
    homozygote_count: int | None = Field(None, description="Number of homozygotes")
    hemizygote_count: int | None = Field(None, description="Number of hemizygotes")
    filters: list[str] = Field(default_factory=list, description="Applied filters")
    populations: list[SVPopulation] = Field(
        default_factory=list, description="Population frequencies"
    )
    consequences: list[SVConsequence] = Field(
        default_factory=list, description="Variant consequences"
    )
    copy_numbers: list[SVCopyNumber] | None = Field(None, description="Copy number data")
    cpx_intervals: list[dict[str, Any]] | None = Field(None, description="Complex intervals")
    cpx_type: str | None = Field(None, description="Complex variant type")
    evidence: list[str] | None = Field(None, description="Supporting evidence")
    genes: list[str] | None = Field(None, description="Affected genes")
    major_consequence: str | None = Field(None, description="Most severe consequence")
    qual: float | None = Field(None, description="Quality score")
