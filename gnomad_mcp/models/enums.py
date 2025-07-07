"""Enum definitions for gnomAD API."""

from enum import Enum


class GnomadDataset(str, Enum):
    """Available gnomAD datasets."""

    GNOMAD_R2_1 = "gnomad_r2_1"
    GNOMAD_R3 = "gnomad_r3"
    GNOMAD_R4 = "gnomad_r4"

    @classmethod
    def get_default(cls):
        """Get the default dataset."""
        return cls.GNOMAD_R4


class StructuralVariantDataset(str, Enum):
    """Available structural variant datasets."""

    GNOMAD_SV_R2_1 = "gnomad_sv_r2_1"
    GNOMAD_SV_R4 = "gnomad_sv_r4"

    @classmethod
    def get_default(cls):
        """Get the default SV dataset."""
        return cls.GNOMAD_SV_R4


class ReferenceGenome(str, Enum):
    """Available reference genomes."""

    GRCH37 = "GRCh37"
    GRCH38 = "GRCh38"

    @classmethod
    def get_default(cls):
        """Get the default reference genome."""
        return cls.GRCH38
