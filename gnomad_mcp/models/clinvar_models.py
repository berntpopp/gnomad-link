"""Data models for ClinVar variant queries."""

from typing import List, Optional

from pydantic import BaseModel, Field


class ClinVarCondition(BaseModel):
    """Condition associated with a ClinVar submission."""

    name: str = Field(..., description="Condition name")
    medgen_id: Optional[str] = Field(None, description="MedGen identifier")


class ClinVarSubmission(BaseModel):
    """Individual submission to ClinVar."""

    clinical_significance: Optional[str] = Field(
        None, description="Clinical significance"
    )
    last_evaluated: Optional[str] = Field(None, description="Last evaluation date")
    review_status: Optional[str] = Field(None, description="Review status")
    submitter_name: Optional[str] = Field(None, description="Name of submitter")
    conditions: List[ClinVarCondition] = Field(
        default_factory=list, description="Associated conditions"
    )


class GnomadInClinVar(BaseModel):
    """gnomAD data for a ClinVar variant."""

    exome: Optional[dict] = Field(None, description="Exome data")
    genome: Optional[dict] = Field(None, description="Genome data")


class ClinVarVariant(BaseModel):
    """ClinVar variant information."""

    variant_id: str = Field(..., description="Variant identifier")
    reference_genome: str = Field(..., description="Reference genome")
    chrom: str = Field(..., description="Chromosome")
    pos: int = Field(..., description="Position")
    ref: str = Field(..., description="Reference allele")
    alt: str = Field(..., description="Alternate allele")
    clinical_significance: Optional[str] = Field(
        None, description="Overall clinical significance"
    )
    clinvar_variation_id: Optional[str] = Field(
        None, description="ClinVar variation ID"
    )
    gnomad: Optional[GnomadInClinVar] = Field(None, description="gnomAD data")
    gold_stars: Optional[int] = Field(None, description="ClinVar review status stars")
    in_gnomad: Optional[bool] = Field(None, description="Whether variant is in gnomAD")
    last_evaluated: Optional[str] = Field(None, description="Last evaluation date")
    review_status: Optional[str] = Field(None, description="Review status")
    rsid: Optional[str] = Field(None, description="dbSNP rsID")
    submissions: List[ClinVarSubmission] = Field(
        default_factory=list, description="Individual submissions"
    )
