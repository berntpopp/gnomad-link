"""Data models for gene-related queries."""

from pydantic import BaseModel, Field


class GeneExon(BaseModel):
    """Exon information for a gene."""

    feature_type: str = Field(..., description="Type of feature (e.g., CDS, UTR)")
    start: int = Field(..., description="Start position")
    stop: int = Field(..., description="End position")


class GeneTranscript(BaseModel):
    """Transcript information for a gene."""

    transcript_id: str = Field(..., description="Transcript identifier")
    transcript_version: str | None = Field(None, description="Transcript version")
    chrom: str = Field(..., description="Chromosome")
    start: int = Field(..., description="Start position")
    stop: int = Field(..., description="End position")
    strand: str | None = Field(None, description="Strand (+ or -)")
    exons: list[GeneExon] = Field(default_factory=list, description="List of exons")


class GeneConstraint(BaseModel):
    """Gene constraint scores from gnomAD."""

    exp_lof: float | None = Field(None, description="Expected loss-of-function variants")
    exp_mis: float | None = Field(None, description="Expected missense variants")
    exp_syn: float | None = Field(None, description="Expected synonymous variants")
    obs_lof: int | None = Field(None, description="Observed loss-of-function variants")
    obs_mis: int | None = Field(None, description="Observed missense variants")
    obs_syn: int | None = Field(None, description="Observed synonymous variants")
    oe_lof: float | None = Field(None, description="Observed/expected ratio for LoF")
    oe_lof_lower: float | None = Field(None, description="Lower bound of LoF o/e")
    oe_lof_upper: float | None = Field(None, description="Upper bound of LoF o/e")
    oe_mis: float | None = Field(None, description="Observed/expected ratio for missense")
    oe_mis_lower: float | None = Field(None, description="Lower bound of missense o/e")
    oe_mis_upper: float | None = Field(None, description="Upper bound of missense o/e")
    oe_syn: float | None = Field(None, description="Observed/expected ratio for synonymous")
    oe_syn_lower: float | None = Field(None, description="Lower bound of synonymous o/e")
    oe_syn_upper: float | None = Field(None, description="Upper bound of synonymous o/e")
    lof_z: float | None = Field(None, description="Z-score for LoF")
    mis_z: float | None = Field(None, description="Z-score for missense")
    syn_z: float | None = Field(None, description="Z-score for synonymous")
    pli: float | None = Field(None, description="Probability of LoF intolerance", alias="pLI")

    model_config = {"populate_by_name": True}


class Gene(BaseModel):
    """Gene information from gnomAD."""

    gene_id: str = Field(..., description="Ensembl gene ID")
    symbol: str = Field(..., description="Gene symbol")
    name: str | None = Field(None, description="Full gene name")
    canonical_transcript_id: str | None = Field(
        None, description="Canonical transcript", alias="canonical_transcript"
    )
    chrom: str = Field(..., description="Chromosome")
    start: int = Field(..., description="Start position")
    stop: int = Field(..., description="End position")
    strand: str | None = Field(None, description="Strand (+ or -)")
    exons: list[GeneExon] = Field(default_factory=list, description="Gene exons")
    transcripts: list[GeneTranscript] = Field(default_factory=list, description="Gene transcripts")
    gnomad_constraint: GeneConstraint | None = Field(None, description="gnomAD constraint metrics")
    flags: list[str] = Field(default_factory=list, description="Gene flags")

    model_config = {"populate_by_name": True}


class GeneSearchResult(BaseModel):
    """Result from gene search query."""

    ensembl_id: str = Field(..., description="Ensembl gene ID")
    ensembl_version: str | None = Field(None, description="Ensembl version")
    symbol: str = Field(..., description="Gene symbol")
