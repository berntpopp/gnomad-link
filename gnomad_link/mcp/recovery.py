"""Recovery-path helpers for MCP error envelopes (kept out of errors.py; LOC budget)."""

from __future__ import annotations

from typing import Any

# Maps each dataset to its reference build so error/success envelopes can echo a
# self-contained provenance pointer (which release + which build the call hit).
DATASET_BUILD = {
    "gnomad_r2_1": "GRCh37",
    "gnomad_r3": "GRCh38",
    "gnomad_r4": "GRCh38",
    "gnomad_sv_r2_1": "GRCh37",
    "gnomad_sv_r4": "GRCh38",
}


def liftover_recovery_command(
    internal_code: str, fallback_tool: str | None, *, variant_id: str | None, dataset: str | None
) -> dict[str, Any] | None:
    """Surface compute_variant_liftover on a well-formed variant that was not_found.

    Build mismatch (a GRCh37 coordinate queried against a GRCh38 dataset, or vice
    versa) is the single most common coordinate error, and resolve_variant_id is a
    dead end for a coordinate that only exists in the OTHER build. When the
    not_found fallback is the variant resolver (i.e. a well-formed variant id is in
    context), also offer a liftover to the other build (defect #45-4).
    """
    if internal_code != "not_found" or fallback_tool != "resolve_variant_id" or not variant_id:
        return None
    build = DATASET_BUILD.get(dataset or "")
    # If the id was absent from a GRCh38 dataset it is most likely a GRCh37
    # coordinate (and vice versa); source_genome names the build to convert FROM.
    source_genome = "GRCh38" if build == "GRCh37" else "GRCh37"
    return {
        "tool": "compute_variant_liftover",
        "arguments": {"source_variant_id": variant_id, "source_genome": source_genome},
    }
