"""Data models for mitochondrial variant queries."""

from typing import Any

from pydantic import BaseModel, Field


class MitochondrialPopulation(BaseModel):
    """Population data for mitochondrial variants."""

    id: str = Field(..., description="Population identifier")
    an: int = Field(..., description="Allele number")
    ac_het: int = Field(..., description="Heteroplasmic allele count")
    ac_hom: int = Field(..., description="Homoplasmic allele count")
    heteroplasmy_distribution: dict[str, Any] | None = Field(
        None, description="Distribution of heteroplasmy levels"
    )


class MitochondrialHaplogroup(BaseModel):
    """Haplogroup data for mitochondrial variants."""

    id: str = Field(..., description="Haplogroup identifier")
    an: int = Field(..., description="Allele number")
    ac_het: int = Field(..., description="Heteroplasmic allele count")
    ac_hom: int = Field(..., description="Homoplasmic allele count")
    faf: float | None = Field(None, description="Filtering allele frequency")
    faf_hom: float | None = Field(None, description="Filtering AF for homoplasmic")


class MitochondrialTranscriptConsequence(BaseModel):
    """Transcript consequence for mitochondrial variants."""

    consequence_terms: list[str] = Field(default_factory=list, description="Consequence terms")
    gene_id: str | None = Field(None, description="Gene ID")
    gene_symbol: str | None = Field(None, description="Gene symbol")
    transcript_id: str | None = Field(None, description="Transcript ID")
    hgvs: str | None = Field(None, description="HGVS notation")
    hgvsc: str | None = Field(None, description="HGVS coding sequence")
    hgvsp: str | None = Field(None, description="HGVS protein")
    lof: str | None = Field(None, description="Loss of function prediction")
    lof_filter: str | None = Field(None, description="LoF filter")
    lof_flags: str | None = Field(None, description="LoF flags")
    major_consequence: str | None = Field(None, description="Major consequence")
    polyphen_prediction: str | None = Field(None, description="PolyPhen prediction")
    sift_prediction: str | None = Field(None, description="SIFT prediction")
    is_canonical: bool | None = Field(None, description="Is canonical transcript")


class MitochondrialVariant(BaseModel):
    """Mitochondrial variant information."""

    variant_id: str = Field(..., description="Variant identifier")
    pos: int = Field(..., description="Position")
    ref: str = Field(..., description="Reference allele")
    alt: str = Field(..., description="Alternate allele")
    ac_het: int = Field(..., description="Heteroplasmic allele count")
    ac_hom: int = Field(..., description="Homoplasmic allele count")
    ac_hom_mnv: int | None = Field(None, description="Homoplasmic MNV allele count")
    an: int = Field(..., description="Allele number")
    max_heteroplasmy: float | None = Field(None, description="Maximum heteroplasmy level")
    filters: list[str] = Field(default_factory=list, description="Applied filters")
    flags: list[str] = Field(default_factory=list, description="Variant flags")
    excluded_ac: int | None = Field(None, description="Excluded allele count")
    haplogroup_defining: bool | None = Field(None, description="Is haplogroup defining")
    rsid: str | None = Field(None, description="dbSNP rsID")
    rsids: list[str] = Field(default_factory=list, description="All rsIDs")
    mitotip_score: float | None = Field(None, description="MitoTIP score")
    mitotip_trna_prediction: str | None = Field(None, description="MitoTIP tRNA prediction")
    pon_ml_probability_of_pathogenicity: float | None = Field(
        None, description="PON-ML pathogenicity probability"
    )
    pon_mt_trna_prediction: str | None = Field(None, description="PON-mt-tRNA prediction")
    populations: list[MitochondrialPopulation] = Field(
        default_factory=list, description="Population data"
    )
    haplogroups: list[MitochondrialHaplogroup] = Field(
        default_factory=list, description="Haplogroup data"
    )
    age_distribution: dict[str, Any] | None = Field(None, description="Age distribution")
    heteroplasmy_distribution: dict[str, Any] | None = Field(
        None, description="Heteroplasmy distribution"
    )
    site_quality_metrics: list[dict[str, Any]] | None = Field(
        None, description="Site quality metrics"
    )
    transcript_consequences: list[MitochondrialTranscriptConsequence] = Field(
        default_factory=list, description="Transcript consequences"
    )
