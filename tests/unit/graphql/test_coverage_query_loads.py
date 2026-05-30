from __future__ import annotations

from gnomad_link.graphql.query_loader import QueryLoader


def test_coverage_query_file_loads_for_v4() -> None:
    loader = QueryLoader()
    doc = loader.load_query("coverage", "v4")
    assert "coverage" in doc


def test_coverage_query_defines_three_named_operations() -> None:
    loader = QueryLoader()
    doc = loader.load_query("coverage", "v4")
    assert "query gene_coverage(" in doc
    assert "query region_coverage(" in doc
    assert "query variant_coverage(" in doc


def test_region_coverage_requires_dataset_argument() -> None:
    loader = QueryLoader()
    doc = loader.load_query("coverage", "v4")
    # region.coverage takes a non-null DatasetId; gene/variant accept the nullable form.
    assert "$dataset: DatasetId!" in doc
