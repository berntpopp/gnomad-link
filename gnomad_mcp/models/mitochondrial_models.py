"""Data models for mitochondrial variant queries."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class MitochondrialPopulation(BaseModel):
    """Population data for mitochondrial variants."""

    id: str = Field(..., description="Population identifier")
    an: int = Field(..., description="Allele number")
    ac_het: int = Field(..., description="Heteroplasmic allele count")
    ac_hom: int = Field(..., description="Homoplasmic allele count")
    heteroplasmy_distribution: Optional[Dict[str, Any]] = Field(
        None, description="Distribution of heteroplasmy levels"
    )


class MitochondrialHaplogroup(BaseModel):
    """Haplogroup data for mitochondrial variants."""

    id: str = Field(..., description="Haplogroup identifier")
    an: int = Field(..., description="Allele number")
    ac_het: int = Field(..., description="Heteroplasmic allele count")
    ac_hom: int = Field(..., description="Homoplasmic allele count")
    faf: Optional[float] = Field(None, description="Filtering allele frequency")
    faf_hom: Optional[float] = Field(None, description="Filtering AF for homoplasmic")


class MitochondrialTranscriptConsequence(BaseModel):
    """Transcript consequence for mitochondrial variants."""

    consequence_terms: List[str] = Field(
        default_factory=list, description="Consequence terms"
    )
    gene_id: Optional[str] = Field(None, description="Gene ID")
    gene_symbol: Optional[str] = Field(None, description="Gene symbol")
    transcript_id: Optional[str] = Field(None, description="Transcript ID")
    hgvs: Optional[str] = Field(None, description="HGVS notation")
    hgvsc: Optional[str] = Field(None, description="HGVS coding sequence")
    hgvsp: Optional[str] = Field(None, description="HGVS protein")
    lof: Optional[str] = Field(None, description="Loss of function prediction")
    lof_filter: Optional[str] = Field(None, description="LoF filter")
    lof_flags: Optional[str] = Field(None, description="LoF flags")
    major_consequence: Optional[str] = Field(None, description="Major consequence")
    polyphen_prediction: Optional[str] = Field(None, description="PolyPhen prediction")
    sift_prediction: Optional[str] = Field(None, description="SIFT prediction")
    is_canonical: Optional[bool] = Field(None, description="Is canonical transcript")


class MitochondrialVariant(BaseModel):
    """Mitochondrial variant information."""

    variant_id: str = Field(..., description="Variant identifier")
    pos: int = Field(..., description="Position")
    ref: str = Field(..., description="Reference allele")
    alt: str = Field(..., description="Alternate allele")
    ac_het: int = Field(..., description="Heteroplasmic allele count")
    ac_hom: int = Field(..., description="Homoplasmic allele count")
    ac_hom_mnv: Optional[int] = Field(None, description="Homoplasmic MNV allele count")
    an: int = Field(..., description="Allele number")
    max_heteroplasmy: Optional[float] = Field(
        None, description="Maximum heteroplasmy level"
    )
    filters: List[str] = Field(default_factory=list, description="Applied filters")
    flags: List[str] = Field(default_factory=list, description="Variant flags")
    excluded_ac: Optional[int] = Field(None, description="Excluded allele count")
    haplogroup_defining: Optional[bool] = Field(
        None, description="Is haplogroup defining"
    )
    rsid: Optional[str] = Field(None, description="dbSNP rsID")
    rsids: List[str] = Field(default_factory=list, description="All rsIDs")
    mitotip_score: Optional[float] = Field(None, description="MitoTIP score")
    mitotip_trna_prediction: Optional[str] = Field(
        None, description="MitoTIP tRNA prediction"
    )
    pon_ml_probability_of_pathogenicity: Optional[float] = Field(
        None, description="PON-ML pathogenicity probability"
    )
    pon_mt_trna_prediction: Optional[str] = Field(
        None, description="PON-mt-tRNA prediction"
    )
    populations: List[MitochondrialPopulation] = Field(
        default_factory=list, description="Population data"
    )
    haplogroups: List[MitochondrialHaplogroup] = Field(
        default_factory=list, description="Haplogroup data"
    )
    age_distribution: Optional[Dict[str, Any]] = Field(
        None, description="Age distribution"
    )
    heteroplasmy_distribution: Optional[Dict[str, Any]] = Field(
        None, description="Heteroplasmy distribution"
    )
    site_quality_metrics: Optional[List[Dict[str, Any]]] = Field(
        None, description="Site quality metrics"
    )
    transcript_consequences: List[MitochondrialTranscriptConsequence] = Field(
        default_factory=list, description="Transcript consequences"
    )
