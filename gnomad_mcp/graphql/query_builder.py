"""GraphQL query builder with version support."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class QueryBuilder:
    """Build and validate GraphQL queries for different gnomAD versions."""

    # Dataset to version mapping
    DATASET_VERSIONS = {
        "gnomad_r2_1": "v2",
        "gnomad_r3": "v3",
        "gnomad_r4": "v4",
        "gnomad_sv_r2_1": "v2",
        "gnomad_sv_r4": "v4",
        "gnomad_cnv_r4": "v4",
    }

    # Reference genomes by version
    REFERENCE_GENOMES = {
        "v2": "GRCh37",
        "v3": "GRCh38",
        "v4": "GRCh38",
    }

    @classmethod
    def get_version_for_dataset(cls, dataset: str) -> str:
        """Get API version for a dataset."""
        return cls.DATASET_VERSIONS.get(dataset, "v4")

    @classmethod
    def get_reference_genome(cls, version: str) -> str:
        """Get reference genome for a version."""
        return cls.REFERENCE_GENOMES.get(version, "GRCh38")

    @classmethod
    def validate_variant_id(cls, variant_id: str) -> bool:
        """Validate variant ID format."""
        if not variant_id:
            raise ValueError("Variant ID cannot be empty")
        parts = variant_id.split("-")
        if len(parts) != 4:
            raise ValueError(
                f"Invalid variant ID: {variant_id}. "
                "Expected format: chromosome-position-reference-alternate"
            )
        return True

    @classmethod
    def process_variables(
        cls, query_type: str, variables: dict[str, Any], version: str = "v4"
    ) -> dict[str, Any]:
        """Process and validate variables for a query type."""
        processed = variables.copy()

        # Handle variant_id conversion based on query type
        if query_type == "variant":
            # Regular variant queries use camelCase
            if "variant_id" in processed and "variantId" not in processed:
                processed["variantId"] = processed.pop("variant_id")
            cls.validate_variant_id(processed.get("variantId", ""))
        elif query_type in ["clinvar_variant", "mitochondrial_variant"]:
            # ClinVar and mitochondrial queries use snake_case
            if "variantId" in processed and "variant_id" not in processed:
                processed["variant_id"] = processed.pop("variantId")
            cls.validate_variant_id(processed.get("variant_id", ""))

        elif query_type in ["gene", "gene_search", "clinvar_variant", "gene_variants"]:
            # Add reference genome if not provided
            if "reference_genome" not in processed:
                processed["reference_genome"] = cls.get_reference_genome(version)
            # Map GRCh37/38 to the enum values expected by the API
            if processed.get("reference_genome") == "GRCh37":
                processed["reference_genome"] = "GRCh37"
            elif processed.get("reference_genome") == "GRCh38":
                processed["reference_genome"] = "GRCh38"

        elif query_type == "region":
            # Validate region parameters
            if not all(k in processed for k in ["chrom", "start", "stop"]):
                raise ValueError("Region query requires chrom, start, and stop")
            # Add reference genome if needed
            if "reference_genome" not in processed:
                processed["reference_genome"] = cls.get_reference_genome(version)

        return processed
