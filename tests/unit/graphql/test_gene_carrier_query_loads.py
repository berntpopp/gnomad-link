from __future__ import annotations

from gnomad_link.graphql.query_loader import QueryLoader


def test_gene_carrier_query_loads_for_v4() -> None:
    loader = QueryLoader()
    doc = loader.load_query("gene_carrier_variants", "v4")
    assert "query gene_carrier_variants(" in doc
    assert "variants(dataset: $dataset)" in doc


def test_gene_carrier_query_selects_per_population_homozygote_count() -> None:
    loader = QueryLoader()
    doc = loader.load_query("gene_carrier_variants", "v4")
    # populations block must carry ac, an AND homozygote_count for VCR/GCR.
    assert "homozygote_count" in doc
    assert "populations {" in doc


def test_gene_carrier_query_selects_transcript_consequence_for_lof() -> None:
    loader = QueryLoader()
    doc = loader.load_query("gene_carrier_variants", "v4")
    assert "transcript_consequence {" in doc
    assert "is_canonical" in doc
    assert "lof" in doc
    assert "consequence_terms" in doc


def test_gene_carrier_query_selects_clinvar_variants() -> None:
    loader = QueryLoader()
    doc = loader.load_query("gene_carrier_variants", "v4")
    assert "clinvar_variants {" in doc
    assert "clinical_significance" in doc
    assert "gold_stars" in doc
