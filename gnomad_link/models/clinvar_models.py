"""Data models for ClinVar variant queries."""

from pydantic import BaseModel, Field


class ClinVarCondition(BaseModel):
    """Condition associated with a ClinVar submission."""

    name: str = Field(..., description="Condition name")
    medgen_id: str | None = Field(None, description="MedGen identifier")


class ClinVarSubmission(BaseModel):
    """Individual submission to ClinVar."""

    clinical_significance: str | None = Field(None, description="Clinical significance")
    last_evaluated: str | None = Field(None, description="Last evaluation date")
    review_status: str | None = Field(None, description="Review status")
    submitter_name: str | None = Field(None, description="Name of submitter")
    conditions: list[ClinVarCondition] = Field(
        default_factory=list, description="Associated conditions"
    )


class GnomadInClinVar(BaseModel):
    """gnomAD data for a ClinVar variant."""

    exome: dict | None = Field(None, description="Exome data")
    genome: dict | None = Field(None, description="Genome data")


class ClinVarVariant(BaseModel):
    """ClinVar variant information."""

    variant_id: str = Field(..., description="Variant identifier")
    reference_genome: str = Field(..., description="Reference genome")
    chrom: str = Field(..., description="Chromosome")
    pos: int = Field(..., description="Position")
    ref: str = Field(..., description="Reference allele")
    alt: str = Field(..., description="Alternate allele")
    clinical_significance: str | None = Field(None, description="Overall clinical significance")
    clinvar_variation_id: str | None = Field(None, description="ClinVar variation ID")
    gnomad: GnomadInClinVar | None = Field(None, description="gnomAD data")
    gold_stars: int | None = Field(None, description="ClinVar review status stars")
    in_gnomad: bool | None = Field(None, description="Whether variant is in gnomAD")
    last_evaluated: str | None = Field(None, description="Last evaluation date")
    review_status: str | None = Field(None, description="Review status")
    rsid: str | None = Field(None, description="dbSNP rsID")
    submissions: list[ClinVarSubmission] = Field(
        default_factory=list, description="Individual submissions"
    )
