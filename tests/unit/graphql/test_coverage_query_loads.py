from __future__ import annotations

import pytest

from gnomad_link.graphql.query_loader import QueryLoader


def test_gene_coverage_query_loads_single_operation() -> None:
    loader = QueryLoader()
    doc = loader.load_query("coverage_gene", "v4")
    assert "query gene_coverage(" in doc
    # Single-op document: must NOT declare the region/variant operations.
    assert "query region_coverage(" not in doc
    assert "query variant_coverage(" not in doc


def test_region_coverage_query_loads_single_operation() -> None:
    loader = QueryLoader()
    doc = loader.load_query("coverage_region", "v4")
    assert "query region_coverage(" in doc
    # region.coverage takes a non-null DatasetId.
    assert "$dataset: DatasetId!" in doc
    assert "query gene_coverage(" not in doc
    assert "query variant_coverage(" not in doc


def test_variant_coverage_query_loads_single_operation() -> None:
    loader = QueryLoader()
    doc = loader.load_query("coverage_variant", "v4")
    assert "query variant_coverage(" in doc
    assert "query gene_coverage(" not in doc
    assert "query region_coverage(" not in doc


def test_gene_coverage_does_not_leak_region_chrom_variable() -> None:
    # Regression guard: the live gnomAD API validates required variables across the
    # whole document, so a multi-op doc made gene requests fail because region's
    # required `$chrom: String!` was unprovided. Each scope must be its own doc.
    loader = QueryLoader()
    doc = loader.load_query("coverage_gene", "v4")
    assert "$chrom" not in doc


def test_legacy_combined_coverage_document_is_removed() -> None:
    loader = QueryLoader()
    with pytest.raises(FileNotFoundError):
        loader.load_query("coverage", "v4")
