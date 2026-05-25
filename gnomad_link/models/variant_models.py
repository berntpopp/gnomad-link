"""Pydantic models for variant frequency data."""

from pydantic import BaseModel, ConfigDict, Field


class PopulationFrequency(BaseModel):
    """Frequency data for a specific population."""

    name: str = Field(..., description="Name of the population group (e.g., 'afr').", alias="id")
    allele_count: int = Field(..., description="Number of alternate alleles observed.", alias="ac")
    allele_number: int = Field(..., description="Total number of alleles assessed.", alias="an")
    homozygote_count: int = Field(..., description="Number of homozygous individuals.")

    @property
    def allele_frequency(self) -> float | None:
        """Calculate allele frequency (AF) from AC/AN."""
        if self.allele_number > 0:
            return self.allele_count / self.allele_number
        return None

    @property
    def id(self) -> str:
        """Return the population ID (alias for name)."""
        return self.name

    model_config = {"populate_by_name": True}  # Allows using alias 'ac' to populate 'allele_count'


class VariantDataSource(BaseModel):
    """Variant data from a specific sequencing source (exome or genome)."""

    ac: int = Field(0, description="Total allele count")
    an: int = Field(0, description="Total allele number")
    homozygote_count: int = Field(0, description="Total homozygote count")
    hemizygote_count: int | None = Field(
        None, description="Total hemizygote count (for X-linked variants)"
    )
    populations: list[PopulationFrequency] = Field(
        default_factory=list, description="Population-specific frequency data."
    )

    @property
    def total_allele_count(self) -> int:
        """Sum of allele counts across all populations."""
        return sum(pop.allele_count for pop in self.populations)

    @property
    def total_allele_number(self) -> int:
        """Sum of allele numbers across all populations."""
        return sum(pop.allele_number for pop in self.populations)

    @property
    def overall_frequency(self) -> float | None:
        """Calculate overall allele frequency across all populations."""
        if self.total_allele_number > 0:
            return self.total_allele_count / self.total_allele_number
        return None


class VariantFrequencyResponse(BaseModel):
    """Complete variant frequency response."""

    variant_id: str = Field(..., description="Variant identifier (e.g., '1-55039447-G-T').")
    dataset: str = Field(..., description="gnomAD dataset ID (e.g., 'gnomad_r4').")
    exome: VariantDataSource | None = Field(
        None, description="Frequency data from exome sequencing."
    )
    genome: VariantDataSource | None = Field(
        None, description="Frequency data from genome sequencing."
    )
    gene_symbol: str | None = Field(
        None,
        description="HGNC gene symbol from the canonical transcript consequence, when present.",
    )
    major_consequence: str | None = Field(
        None,
        description="VEP major_consequence from the canonical transcript consequence, when present.",
    )

    @property
    def has_data(self) -> bool:
        """Check if variant has any meaningful frequency data."""
        has_exome_data = self.exome is not None and (
            self.exome.total_allele_count > 0
            or self.exome.total_allele_number > 0
            or len(self.exome.populations) > 0
        )
        has_genome_data = self.genome is not None and (
            self.genome.total_allele_count > 0
            or self.genome.total_allele_number > 0
            or len(self.genome.populations) > 0
        )
        return has_exome_data or has_genome_data

    model_config = {
        "json_schema_extra": {
            "example": {
                "variant_id": "1-55039447-G-T",
                "dataset": "gnomad_r4",
                "exome": {
                    "populations": [
                        {
                            "name": "afr",
                            "allele_count": 2,
                            "allele_number": 15300,
                            "homozygote_count": 0,
                        },
                        {
                            "name": "eas",
                            "allele_count": 0,
                            "allele_number": 19950,
                            "homozygote_count": 0,
                        },
                    ]
                },
                "genome": None,
            }
        }
    }


class VariantSearchResult(BaseModel):
    """Minimal result from resolve_variant_id / search_variants -- IDs only."""

    variant_id: str = Field(..., description="gnomAD variant ID (CHROM-POS-REF-ALT)")
    rsid: str | None = None
    dataset: str | None = None


class VariantDetails(BaseModel):
    """Compact variant detail payload returned by get_variant_details in compact mode."""

    variant_id: str
    reference_genome: str | None = None
    pos: int | None = None
    ref: str | None = None
    alt: str | None = None
    rsids: list[str] = Field(default_factory=list)
    major_consequence: str | None = None
    transcript_consequences: list[dict] | None = None
    in_silico_predictors: dict | None = None
    clinvar: dict | None = None
    exome: dict | None = None
    genome: dict | None = None

    model_config = ConfigDict(extra="allow")
