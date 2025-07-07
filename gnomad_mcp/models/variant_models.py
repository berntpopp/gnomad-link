"""Pydantic models for variant frequency data."""

from typing import List, Optional

from pydantic import BaseModel, Field


class PopulationFrequency(BaseModel):
    """Frequency data for a specific population."""

    name: str = Field(
        ..., description="Name of the population group (e.g., 'afr').", alias="id"
    )
    allele_count: int = Field(
        ..., description="Number of alternate alleles observed.", alias="ac"
    )
    allele_number: int = Field(
        ..., description="Total number of alleles assessed.", alias="an"
    )
    homozygote_count: int = Field(..., description="Number of homozygous individuals.")

    @property
    def allele_frequency(self) -> Optional[float]:
        """Calculate allele frequency (AF) from AC/AN."""
        if self.allele_number > 0:
            return self.allele_count / self.allele_number
        return None

    model_config = {
        "populate_by_name": True
    }  # Allows using alias 'ac' to populate 'allele_count'


class VariantDataSource(BaseModel):
    """Variant data from a specific sequencing source (exome or genome)."""

    populations: List[PopulationFrequency] = Field(
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
    def overall_frequency(self) -> Optional[float]:
        """Calculate overall allele frequency across all populations."""
        if self.total_allele_number > 0:
            return self.total_allele_count / self.total_allele_number
        return None


class VariantFrequencyResponse(BaseModel):
    """Complete variant frequency response."""

    variant_id: str = Field(
        ..., description="Variant identifier (e.g., '1-55039447-G-T')."
    )
    dataset: str = Field(..., description="gnomAD dataset ID (e.g., 'gnomad_r4').")
    exome: Optional[VariantDataSource] = Field(
        None, description="Frequency data from exome sequencing."
    )
    genome: Optional[VariantDataSource] = Field(
        None, description="Frequency data from genome sequencing."
    )

    @property
    def has_data(self) -> bool:
        """Check if variant has any frequency data."""
        return self.exome is not None or self.genome is not None

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
