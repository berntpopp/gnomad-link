"""Tests for the GraphQL query builder."""

import pytest

from gnomad_link.graphql.query_builder import QueryBuilder


class TestQueryBuilder:
    """Test GraphQL query builder functionality."""

    def test_get_version_for_dataset(self):
        """Test dataset to version mapping."""
        assert QueryBuilder.get_version_for_dataset("gnomad_r2_1") == "v2"
        assert QueryBuilder.get_version_for_dataset("gnomad_r3") == "v3"
        assert QueryBuilder.get_version_for_dataset("gnomad_r4") == "v4"
        assert QueryBuilder.get_version_for_dataset("unknown") == "v4"  # Default

    def test_get_reference_genome(self):
        """Test reference genome mapping."""
        assert QueryBuilder.get_reference_genome("v2") == "GRCh37"
        assert QueryBuilder.get_reference_genome("v3") == "GRCh38"
        assert QueryBuilder.get_reference_genome("v4") == "GRCh38"
        assert QueryBuilder.get_reference_genome("v5") == "GRCh38"  # Default

    def test_validate_variant_id(self):
        """Test variant ID validation."""
        # Valid variant IDs - should not raise
        assert QueryBuilder.validate_variant_id("1-12345-A-G") is True
        assert QueryBuilder.validate_variant_id("X-12345-AT-A") is True
        assert QueryBuilder.validate_variant_id("22-12345-ATCG-A") is True
        assert QueryBuilder.validate_variant_id("M-8602-T-C") is True

        # Invalid variant IDs - should raise ValueError
        with pytest.raises(ValueError):
            QueryBuilder.validate_variant_id("invalid")
        with pytest.raises(ValueError):
            QueryBuilder.validate_variant_id("1-A-G")
        with pytest.raises(ValueError):
            QueryBuilder.validate_variant_id("")

    def test_process_variables(self):
        """Test variable processing."""
        # Test that process_variables method exists and works
        variables = {"variant_id": "1-12345-A-G", "dataset": "gnomad_r4"}

        # Process variables for variant query
        processed = QueryBuilder.process_variables("variant", variables, "v4")

        # Should return the same or processed variables
        assert isinstance(processed, dict)
        assert "variant_id" in processed or "variantId" in processed

    def test_dataset_version_mapping_comprehensive(self):
        """Test all dataset version mappings."""
        # Test all known datasets
        datasets = {
            "gnomad_r2_1": "v2",
            "gnomad_r3": "v3",
            "gnomad_r4": "v4",
            "gnomad_sv_r2_1": "v2",
            "gnomad_sv_r4": "v4",
            "gnomad_cnv_r4": "v4",
        }

        for dataset, expected_version in datasets.items():
            assert QueryBuilder.get_version_for_dataset(dataset) == expected_version

    def test_variant_id_edge_cases(self):
        """Test variant ID validation edge cases."""
        # Chromosome edge cases - all should pass (4 parts)
        assert QueryBuilder.validate_variant_id("Y-12345-A-G") is True
        assert QueryBuilder.validate_variant_id("MT-8602-T-C") is True
        assert QueryBuilder.validate_variant_id("chrM-8602-T-C") is True

        # Complex variants
        assert QueryBuilder.validate_variant_id("1-12345-ATCGATCG-A") is True
        assert QueryBuilder.validate_variant_id("1-12345-A-ATCGATCG") is True

    def test_process_variables_with_reference_genome(self):
        """Test variable processing with reference genome."""
        variables = {"gene_symbol": "BRCA2", "reference_genome": "GRCh38"}

        # Process for v4 (should keep GRCh38)
        processed = QueryBuilder.process_variables("gene", variables, "v4")
        assert "reference_genome" in processed or "referenceGenome" in processed

    def test_mitochondrial_variant_validation(self):
        """Test mitochondrial variant ID validation."""
        # Various mitochondrial formats - all have 4 parts so should pass
        assert QueryBuilder.validate_variant_id("M-8602-T-C") is True
        assert QueryBuilder.validate_variant_id("MT-8602-T-C") is True
        assert QueryBuilder.validate_variant_id("chrM-8602-T-C") is True
        assert QueryBuilder.validate_variant_id("chrMT-8602-T-C") is True

    def test_structural_variant_datasets(self):
        """Test structural variant dataset mapping."""
        # SV datasets
        assert QueryBuilder.get_version_for_dataset("gnomad_sv_r2_1") == "v2"
        assert QueryBuilder.get_version_for_dataset("gnomad_sv_r4") == "v4"

        # CNV datasets
        assert QueryBuilder.get_version_for_dataset("gnomad_cnv_r4") == "v4"

    def test_invalid_variant_id_formats(self):
        """Test invalid variant ID formats."""
        invalid_ids = [
            "1-12345",  # Only 2 parts
            "1-12345-A",  # Only 3 parts
            "1-12345-A-G-T",  # 5 parts
            "",  # Empty
            "1_12345_A_G",  # Wrong separator
        ]

        for variant_id in invalid_ids:
            with pytest.raises(ValueError):
                QueryBuilder.validate_variant_id(variant_id)
