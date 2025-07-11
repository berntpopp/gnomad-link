"""Data models for the gnomAD MCP server."""

from .clinvar_models import (
    ClinVarCondition,
    ClinVarSubmission,
    ClinVarVariant,
    GnomadInClinVar,
)
from .enums import GnomadDataset, ReferenceGenome, StructuralVariantDataset
from .gene_models import (
    Gene,
    GeneConstraint,
    GeneExon,
    GeneSearchResult,
    GeneTranscript,
)
from .liftover_models import LiftoverResponse, LiftoverResult, LiftoverVariant
from .mitochondrial_models import (
    MitochondrialHaplogroup,
    MitochondrialPopulation,
    MitochondrialTranscriptConsequence,
    MitochondrialVariant,
)
from .structural_variant_models import (
    StructuralVariant,
    SVConsequence,
    SVCopyNumber,
    SVPopulation,
)
from .variant_models import (
    PopulationFrequency,
    VariantDataSource,
    VariantFrequencyResponse,
)

__all__ = [
    # Variant models
    "PopulationFrequency",
    "VariantDataSource",
    "VariantFrequencyResponse",
    # Gene models
    "Gene",
    "GeneConstraint",
    "GeneExon",
    "GeneTranscript",
    "GeneSearchResult",
    # ClinVar models
    "ClinVarVariant",
    "ClinVarCondition",
    "ClinVarSubmission",
    "GnomadInClinVar",
    # Liftover models
    "LiftoverVariant",
    "LiftoverResult",
    "LiftoverResponse",
    # Structural variant models
    "StructuralVariant",
    "SVConsequence",
    "SVCopyNumber",
    "SVPopulation",
    # Mitochondrial models
    "MitochondrialVariant",
    "MitochondrialPopulation",
    "MitochondrialHaplogroup",
    "MitochondrialTranscriptConsequence",
    # Enums
    "GnomadDataset",
    "StructuralVariantDataset",
    "ReferenceGenome",
]
