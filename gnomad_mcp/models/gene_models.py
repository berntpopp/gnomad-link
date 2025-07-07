"""Data models for gene-related queries."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class GeneExon(BaseModel):
    """Exon information for a gene."""

    feature_type: str = Field(..., description="Type of feature (e.g., CDS, UTR)")
    start: int = Field(..., description="Start position")
    stop: int = Field(..., description="End position")


class GeneTranscript(BaseModel):
    """Transcript information for a gene."""

    transcript_id: str = Field(..., description="Transcript identifier")
    transcript_version: Optional[str] = Field(None, description="Transcript version")
    chrom: str = Field(..., description="Chromosome")
    start: int = Field(..., description="Start position")
    stop: int = Field(..., description="End position")
    strand: Optional[str] = Field(None, description="Strand (+ or -)")
    exons: List[GeneExon] = Field(default_factory=list, description="List of exons")


class GeneConstraint(BaseModel):
    """Gene constraint scores from gnomAD."""

    exp_lof: Optional[float] = Field(
        None, description="Expected loss-of-function variants"
    )
    exp_mis: Optional[float] = Field(None, description="Expected missense variants")
    exp_syn: Optional[float] = Field(None, description="Expected synonymous variants")
    obs_lof: Optional[int] = Field(
        None, description="Observed loss-of-function variants"
    )
    obs_mis: Optional[int] = Field(None, description="Observed missense variants")
    obs_syn: Optional[int] = Field(None, description="Observed synonymous variants")
    oe_lof: Optional[float] = Field(None, description="Observed/expected ratio for LoF")
    oe_lof_lower: Optional[float] = Field(None, description="Lower bound of LoF o/e")
    oe_lof_upper: Optional[float] = Field(None, description="Upper bound of LoF o/e")
    oe_mis: Optional[float] = Field(
        None, description="Observed/expected ratio for missense"
    )
    oe_mis_lower: Optional[float] = Field(
        None, description="Lower bound of missense o/e"
    )
    oe_mis_upper: Optional[float] = Field(
        None, description="Upper bound of missense o/e"
    )
    oe_syn: Optional[float] = Field(
        None, description="Observed/expected ratio for synonymous"
    )
    oe_syn_lower: Optional[float] = Field(
        None, description="Lower bound of synonymous o/e"
    )
    oe_syn_upper: Optional[float] = Field(
        None, description="Upper bound of synonymous o/e"
    )
    lof_z: Optional[float] = Field(None, description="Z-score for LoF")
    mis_z: Optional[float] = Field(None, description="Z-score for missense")
    syn_z: Optional[float] = Field(None, description="Z-score for synonymous")
    pli: Optional[float] = Field(
        None, description="Probability of LoF intolerance", alias="pLI"
    )

    model_config = {"populate_by_name": True}


class Gene(BaseModel):
    """Gene information from gnomAD."""

    gene_id: str = Field(..., description="Ensembl gene ID")
    symbol: str = Field(..., description="Gene symbol", alias="name")
    name: Optional[str] = Field(None, description="Full gene name")
    canonical_transcript_id: Optional[str] = Field(
        None, description="Canonical transcript", alias="canonical_transcript"
    )
    chrom: str = Field(..., description="Chromosome")
    start: int = Field(..., description="Start position")
    stop: int = Field(..., description="End position")
    strand: Optional[str] = Field(None, description="Strand (+ or -)")
    exons: List[GeneExon] = Field(default_factory=list, description="Gene exons")
    transcripts: List[GeneTranscript] = Field(
        default_factory=list, description="Gene transcripts"
    )
    gnomad_constraint: Optional[GeneConstraint] = Field(
        None, description="gnomAD constraint metrics"
    )
    flags: List[str] = Field(default_factory=list, description="Gene flags")

    model_config = {"populate_by_name": True}


class GeneSearchResult(BaseModel):
    """Result from gene search query."""

    ensembl_id: str = Field(..., description="Ensembl gene ID")
    ensembl_version: Optional[str] = Field(None, description="Ensembl version")
    symbol: str = Field(..., description="Gene symbol")
