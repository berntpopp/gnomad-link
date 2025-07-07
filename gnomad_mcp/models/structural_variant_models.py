"""Data models for structural variant queries."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SVConsequence(BaseModel):
    """Consequence of a structural variant."""

    consequence: str = Field(..., description="Consequence type")
    genes: List[str] = Field(default_factory=list, description="Affected genes")


class SVCopyNumber(BaseModel):
    """Copy number information for a structural variant."""

    copy_number: int = Field(..., description="Copy number")
    ac: int = Field(..., description="Allele count")


class SVPopulation(BaseModel):
    """Population frequency data for a structural variant."""

    id: str = Field(..., description="Population identifier", alias="id")
    ac: int = Field(..., description="Allele count")
    an: int = Field(..., description="Allele number")
    homozygote_count: Optional[int] = Field(None, description="Number of homozygotes")
    hemizygote_count: Optional[int] = Field(None, description="Number of hemizygotes")


class StructuralVariant(BaseModel):
    """Structural variant information."""

    variant_id: str = Field(..., description="Variant identifier")
    reference_genome: str = Field(..., description="Reference genome")
    chrom: str = Field(..., description="Chromosome")
    chrom2: Optional[str] = Field(
        None, description="Second chromosome (for translocations)"
    )
    pos: int = Field(..., description="Start position")
    pos2: Optional[int] = Field(None, description="Second position")
    end: int = Field(..., description="End position")
    end2: Optional[int] = Field(None, description="Second end position")
    length: Optional[int] = Field(None, description="Length of variant")
    type: str = Field(..., description="Type of structural variant")
    alts: Optional[List[str]] = Field(None, description="Alternate alleles")
    algorithms: Optional[List[str]] = Field(None, description="Detection algorithms")
    ac: int = Field(..., description="Total allele count")
    an: int = Field(..., description="Total allele number")
    af: float = Field(..., description="Allele frequency")
    homozygote_count: Optional[int] = Field(None, description="Number of homozygotes")
    hemizygote_count: Optional[int] = Field(None, description="Number of hemizygotes")
    filters: List[str] = Field(default_factory=list, description="Applied filters")
    populations: List[SVPopulation] = Field(
        default_factory=list, description="Population frequencies"
    )
    consequences: List[SVConsequence] = Field(
        default_factory=list, description="Variant consequences"
    )
    copy_numbers: Optional[List[SVCopyNumber]] = Field(
        None, description="Copy number data"
    )
    cpx_intervals: Optional[List[Dict[str, Any]]] = Field(
        None, description="Complex intervals"
    )
    cpx_type: Optional[str] = Field(None, description="Complex variant type")
    evidence: Optional[List[str]] = Field(None, description="Supporting evidence")
    genes: Optional[List[str]] = Field(None, description="Affected genes")
    major_consequence: Optional[str] = Field(
        None, description="Most severe consequence"
    )
    qual: Optional[float] = Field(None, description="Quality score")
