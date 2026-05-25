"""Pydantic models for liftover data."""

from pydantic import BaseModel, Field

from .enums import ReferenceGenome


class LiftoverVariant(BaseModel):
    """Variant information in a specific reference genome."""

    variant_id: str = Field(..., description="Variant identifier in chr-pos-ref-alt format")
    reference_genome: ReferenceGenome = Field(..., description="Reference genome build")


class LiftoverResult(BaseModel):
    """Result of a liftover operation between reference genomes."""

    source: LiftoverVariant = Field(..., description="Original variant in source reference genome")
    liftover: LiftoverVariant = Field(
        ..., description="Lifted over variant in target reference genome"
    )
    datasets: list[str] = Field(
        default_factory=list,
        description="List of datasets where this liftover mapping is available",
    )


class LiftoverResponse(BaseModel):
    """Response containing liftover results."""

    results: list[LiftoverResult] = Field(
        default_factory=list,
        description="List of liftover results (may be empty if no mapping exists)",
    )
    query_type: str = Field(
        ..., description="Type of liftover query performed: 'forward' or 'reverse'"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "results": [
                    {
                        "source": {
                            "variant_id": "17-7577121-G-A",
                            "reference_genome": "GRCh37",
                        },
                        "liftover": {
                            "variant_id": "17-7673803-G-A",
                            "reference_genome": "GRCh38",
                        },
                        "datasets": ["gnomad_r2_1", "gnomad_r4"],
                    }
                ],
                "query_type": "forward",
            }
        }
    }
