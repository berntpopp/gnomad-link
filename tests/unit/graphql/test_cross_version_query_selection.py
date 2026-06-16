"""Cross-version GraphQL document selection (issue #5, C1).

Characterizes the real production flow used by ``UnifiedGnomadClient``:

    dataset -> QueryBuilder.get_version_for_dataset(dataset) -> version
            -> QueryLoader.load_query(name, version)

These tests are pure and never touch the network. They assert that each
dataset resolves to the correct versioned GraphQL document and that the
version-divergent fields baked into the v2/v3/v4 ``variant``, ``gene``, and
``transcript`` documents are present or absent as the on-disk queries dictate.

They extend (not duplicate) ``test_query_builder.py`` /
``test_query_loader.py``: those cover the mapping table and the loader's
fragment-resolution mechanics in isolation; here we drive the two together
across all three dataset versions and assert on the resolved document text.
"""

from __future__ import annotations

import pytest

from gnomad_link.graphql.query_builder import QueryBuilder
from gnomad_link.graphql.query_loader import QueryLoader

# (dataset, expected version) for the three SNV/indel datasets in scope.
DATASET_TO_VERSION = [
    ("gnomad_r2_1", "v2"),
    ("gnomad_r3", "v3"),
    ("gnomad_r4", "v4"),
]


@pytest.fixture
def loader() -> QueryLoader:
    """A real loader pointed at the bundled production queries directory."""
    return QueryLoader()


@pytest.mark.parametrize("dataset,version", DATASET_TO_VERSION)
def test_dataset_maps_to_version(dataset: str, version: str) -> None:
    assert QueryBuilder.get_version_for_dataset(dataset) == version


@pytest.mark.parametrize("dataset,version", DATASET_TO_VERSION)
def test_variant_document_selected_per_version(
    loader: QueryLoader, dataset: str, version: str
) -> None:
    """The dataset's version selects its own variant.graphql (a real file per version)."""
    version = QueryBuilder.get_version_for_dataset(dataset)
    doc = loader.load_query("variant", version)
    # Every version's variant document is the dataset-parameterized operation.
    assert "query variant($variantId: String!, $dataset: DatasetId!)" in doc
    # Fragment imports are resolved: VariantIdFields is always inlined.
    assert "fragment VariantIdFields on VariantDetails" in doc
    assert "#import" not in doc


@pytest.mark.parametrize("dataset,version", DATASET_TO_VERSION)
def test_in_silico_predictors_only_v3_v4_variant(
    loader: QueryLoader, dataset: str, version: str
) -> None:
    """v2 variant.graphql omits in_silico_predictors; v3 and v4 include it.

    This is the load-bearing version divergence in the variant document: gnomAD
    v2 (GRCh37) exposes no in_silico_predictors block, so requesting it would be
    a schema error upstream. v3/v4 both carry it.
    """
    version = QueryBuilder.get_version_for_dataset(dataset)
    doc = loader.load_query("variant", version)
    if version == "v2":
        assert "in_silico_predictors" not in doc
        assert "fragment InSilicoPredictorFields" not in doc
    else:
        assert "in_silico_predictors {" in doc
        assert "fragment InSilicoPredictorFields on VariantInSilicoPredictor" in doc


@pytest.mark.parametrize("dataset,version", DATASET_TO_VERSION)
def test_variant_transcript_consequence_shape_per_version(
    loader: QueryLoader, dataset: str, version: str
) -> None:
    """v4 uses the TranscriptConsequenceFields fragment; v2/v3 inline the fields.

    v2/v3 variant documents enumerate transcript_consequences inline (and so do
    NOT pull in the TranscriptConsequenceFields fragment), while v4 references the
    shared fragment, which the loader inlines.
    """
    version = QueryBuilder.get_version_for_dataset(dataset)
    doc = loader.load_query("variant", version)
    if version == "v4":
        assert "fragment TranscriptConsequenceFields on TranscriptConsequence" in doc
    else:
        # Inline enumeration -> no TranscriptConsequenceFields fragment pulled in.
        assert "fragment TranscriptConsequenceFields" not in doc
        # ...but the inline fields are present.
        assert "consequence_terms" in doc


@pytest.mark.parametrize("dataset,version", DATASET_TO_VERSION)
def test_gene_variants_block_only_v2_v3(loader: QueryLoader, dataset: str, version: str) -> None:
    """The gene document embeds a dataset-pinned variants() block only for v2/v3.

    v2 pins ``variants(dataset: gnomad_r2_1)`` and v3 pins
    ``variants(dataset: gnomad_r3)`` inside the gene query; v4's gene document
    drops the embedded variants block entirely (variants are fetched separately).
    """
    version = QueryBuilder.get_version_for_dataset(dataset)
    doc = loader.load_query("gene", version)
    if version == "v2":
        assert "variants(dataset: gnomad_r2_1)" in doc
    elif version == "v3":
        assert "variants(dataset: gnomad_r3)" in doc
    else:  # v4
        assert "variants(dataset:" not in doc


@pytest.mark.parametrize("dataset,version", DATASET_TO_VERSION)
def test_gene_top_level_flags_absent_only_v2(
    loader: QueryLoader, dataset: str, version: str
) -> None:
    """Top-level gene ``flags`` exists in v3/v4 but not the v2 gene document."""
    version = QueryBuilder.get_version_for_dataset(dataset)
    doc = loader.load_query("gene", version)
    # All versions always carry the GeneConstraintFields fragment.
    assert "fragment GeneConstraintFields" in doc
    if version == "v2":
        assert "\n        flags\n" not in doc
    else:
        assert "\n        flags\n" in doc


@pytest.mark.parametrize("dataset,version", DATASET_TO_VERSION)
def test_transcript_dataset_param_only_v2(loader: QueryLoader, dataset: str, version: str) -> None:
    """Only the v2 transcript document declares a $dataset variable + variants block.

    v2's transcript query is dataset-parameterized and embeds a variants block;
    v3/v4 transcript documents take only transcript_id + reference_genome.

    Note: every version takes ``$reference_genome`` as a query *argument*; the
    divergence is that v3/v4 also *select* ``reference_genome`` as a returned
    field on the transcript object, while v2 does not.
    """
    version = QueryBuilder.get_version_for_dataset(dataset)
    doc = loader.load_query("transcript", version)
    # The reference_genome argument is present in every version's transcript query.
    assert "$reference_genome: ReferenceGenomeId!" in doc
    if version == "v2":
        assert "$dataset: DatasetId!" in doc
        assert "variants {" in doc
        # v2 does not select reference_genome as a returned field.
        assert "\n        reference_genome\n" not in doc
    else:
        assert "$dataset: DatasetId!" not in doc
        assert "variants {" not in doc
        # v3/v4 select reference_genome as a returned field on the transcript.
        assert "\n        reference_genome\n" in doc


@pytest.mark.parametrize("dataset,version", DATASET_TO_VERSION)
def test_transcript_process_variables_adds_dataset_only_for_v2(dataset: str, version: str) -> None:
    """QueryBuilder injects the gnomad_r2_1 dataset default only for v2 transcripts.

    Mirrors query_builder.process_variables: a v2 transcript call with no
    explicit dataset gets ``dataset='gnomad_r2_1'`` injected (required by the v2
    transcript schema), while v3/v4 transcript calls do not.
    """
    version = QueryBuilder.get_version_for_dataset(dataset)
    processed = QueryBuilder.process_variables(
        "transcript", {"transcript_id": "ENST00000302118"}, version
    )
    # Reference genome is always derived from the version.
    assert processed["reference_genome"] == QueryBuilder.get_reference_genome(version)
    if version == "v2":
        assert processed["dataset"] == "gnomad_r2_1"
    else:
        assert "dataset" not in processed


@pytest.mark.parametrize("dataset,version", DATASET_TO_VERSION)
def test_process_variables_reference_genome_matches_build(dataset: str, version: str) -> None:
    """Gene queries default reference_genome to the version's build (GRCh37 for v2)."""
    version = QueryBuilder.get_version_for_dataset(dataset)
    processed = QueryBuilder.process_variables("gene", {"gene_symbol": "PCSK9"}, version)
    expected = "GRCh37" if version == "v2" else "GRCh38"
    assert processed["reference_genome"] == expected
