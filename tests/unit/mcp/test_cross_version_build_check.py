"""Cross-version build/dataset-mismatch behavior (issue #5, C3).

Deterministic, no-network characterization of the build-mismatch path across
the three SNV/indel datasets. Two layers are covered:

  * gnomad_link.mcp.build_check pure helpers: dataset -> build mapping and
    coordinate-vs-build mismatch detection.
  * gnomad_link.mcp.errors: BuildMismatchError classification into the
    build_mismatch envelope, parametrized by the requesting dataset.

This extends ``test_build_mismatch.py`` (which drives the full MCP facade for a
few hand-picked datasets) by parametrizing the underlying detection + error
classification systematically over r2_1 / r3 / r4. No network is used.
"""

from __future__ import annotations

import pytest

from gnomad_link.mcp.build_check import (
    dataset_build,
    detect_region_mismatch,
    detect_variant_id_mismatch,
)
from gnomad_link.mcp.errors import (
    BuildMismatchError,
    McpErrorContext,
    mcp_tool_error,
)

# (dataset, expected reference build). r2_1 is the only GRCh37 dataset.
DATASET_BUILD = [
    ("gnomad_r2_1", "GRCh37"),
    ("gnomad_r3", "GRCh38"),
    ("gnomad_r4", "GRCh38"),
]

# A coordinate valid only on GRCh37 (chr1 len 249_250_621) but beyond GRCh38
# (248_956_422), and one valid only on GRCh38 (chr5 len 181_538_259) but beyond
# GRCh37 (180_915_260).
GRCH37_ONLY_VARIANT = "1-249100000-A-T"
GRCH38_ONLY_VARIANT = "5-181000000-A-T"
GRCH37_ONLY_REGION = ("1", 249_100_000)
GRCH38_ONLY_REGION = ("5", 181_000_000)


@pytest.mark.parametrize("dataset,build", DATASET_BUILD)
def test_dataset_build_mapping(dataset: str, build: str) -> None:
    assert dataset_build(dataset) == build


@pytest.mark.parametrize("dataset,build", DATASET_BUILD)
def test_variant_mismatch_detection_per_dataset(dataset: str, build: str) -> None:
    """A GRCh37-only coordinate mismatches GRCh38 datasets and matches GRCh37 ones.

    For the GRCh37-only variant: against a GRCh38 dataset (r3/r4) the helper
    infers 'GRCh37' (a mismatch); against the GRCh37 dataset (r2_1) it returns
    None (no mismatch). The GRCh38-only variant is the mirror image.
    """
    g37_result = detect_variant_id_mismatch(GRCH37_ONLY_VARIANT, dataset)
    g38_result = detect_variant_id_mismatch(GRCH38_ONLY_VARIANT, dataset)
    if build == "GRCh37":
        # Dataset already GRCh37: g37 coord matches (None); g38 coord mismatches.
        assert g37_result is None
        assert g38_result == "GRCh38"
    else:
        # Dataset GRCh38: g37 coord mismatches; g38 coord matches (None).
        assert g37_result == "GRCh37"
        assert g38_result is None


@pytest.mark.parametrize("dataset,build", DATASET_BUILD)
def test_region_mismatch_detection_per_dataset(dataset: str, build: str) -> None:
    """detect_region_mismatch mirrors variant detection on (chrom, start)."""
    g37_chrom, g37_start = GRCH37_ONLY_REGION
    g38_chrom, g38_start = GRCH38_ONLY_REGION
    g37_result = detect_region_mismatch(g37_chrom, g37_start, dataset)
    g38_result = detect_region_mismatch(g38_chrom, g38_start, dataset)
    if build == "GRCh37":
        assert g37_result is None
        assert g38_result == "GRCh38"
    else:
        assert g37_result == "GRCh37"
        assert g38_result is None


@pytest.mark.parametrize("dataset,build", DATASET_BUILD)
def test_ambiguous_position_never_mismatches(dataset: str, build: str) -> None:
    """A coordinate within both builds is ambiguous -> None for every dataset."""
    # chr1:55_051_215 is well within both builds.
    assert detect_variant_id_mismatch("1-55051215-G-GA", dataset) is None
    assert detect_region_mismatch("1", 55_051_215, dataset) is None


@pytest.mark.parametrize("dataset,build", DATASET_BUILD)
def test_mitochondrial_coord_never_mismatches(dataset: str, build: str) -> None:
    """Mito coordinates are build-stable: the heuristic returns None for any dataset."""
    assert detect_variant_id_mismatch("M-7497-G-A", dataset) is None
    assert detect_variant_id_mismatch("MT-7497-G-A", dataset) is None


@pytest.mark.parametrize("dataset,build", DATASET_BUILD)
def test_build_mismatch_error_classifies_per_dataset(dataset: str, build: str) -> None:
    """BuildMismatchError -> build_mismatch envelope echoing the dataset's build.

    The inferred (source) build is whichever build the coordinate belongs to,
    i.e. the opposite of the requested dataset's build. The envelope routes to
    compute_variant_liftover with that inferred build as source_genome, and the
    provenance _meta echoes the requested dataset + its reference build.
    """
    inferred_build = "GRCh38" if build == "GRCh37" else "GRCh37"
    variant_id = GRCH38_ONLY_VARIANT if build == "GRCh37" else GRCH37_ONLY_VARIANT
    exc = BuildMismatchError(variant_id=variant_id, inferred_build=inferred_build, dataset=dataset)
    context = McpErrorContext(
        tool_name="get_variant_frequencies", variant_id=variant_id, dataset=dataset
    )
    payload = mcp_tool_error(exc, context).payload

    assert payload["success"] is False
    assert payload["error_code"] == "invalid_input"
    assert payload["error_subtype"] == "build_mismatch"
    assert payload["retryable"] is False
    assert payload["recovery_action"] == "switch_tool"
    assert payload["fallback_tool"] == "compute_variant_liftover"
    assert payload["fallback_args"] == {
        "source_variant_id": variant_id,
        "source_genome": inferred_build,
    }
    # Provenance echoes the requested dataset and its reference build.
    assert payload["_meta"]["dataset"] == dataset
    assert payload["_meta"]["reference_genome"] == build
