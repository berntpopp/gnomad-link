from __future__ import annotations

from gnomad_link.graphql.query_loader import QueryLoader


def test_gene_summary_query_loads_and_resolves_constraint_fragment() -> None:
    loaded = QueryLoader().load_query("gene_summary", "v4")
    # Query head
    assert "query gene_summary(" in loaded
    assert "$gene_symbol: String" in loaded
    assert "$gene_id: String" in loaded
    assert "$reference_genome: ReferenceGenomeId!" in loaded
    # Identity + coordinates
    for field in ("gene_id", "symbol", "name", "chrom", "start", "stop"):
        assert field in loaded
    # Constraint + canonical + MANE
    assert "gnomad_constraint" in loaded
    assert "canonical_transcript_id" in loaded
    assert "mane_select_transcript" in loaded
    assert "refseq_id" in loaded
    # ClinVar variants (no args -> no 100kb cap)
    assert "clinvar_variants {" in loaded
    assert "clinical_significance" in loaded
    assert "gold_stars" in loaded
    # Expression scaffolding (populated on GRCh37, empty on GRCh38)
    assert "pext {" in loaded
    # The GeneConstraintFields fragment must have been inlined.
    assert "fragment GeneConstraintFields on GnomadConstraint" in loaded
    assert "#import" not in loaded
