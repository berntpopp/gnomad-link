"""Cross-dataset comparison tools: compare_variant_across_datasets."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.api import DataNotFoundError, GnomadApiError
from gnomad_link.api.base_client import VariantNotFoundError
from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.comparison_shaping import build_comparison
from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool
from gnomad_link.mcp.headline import comparison_headline
from gnomad_link.mcp.schema_relax import relax_output_schema
from gnomad_link.mcp.shaping import shape_variant_frequencies
from gnomad_link.services import FrequencyService

# Reuse the autosomal grammar from the headline frequency tool. Mitochondrial
# variants are build-stable and not meaningfully comparable across releases here.
_AUTOSOMAL_VARIANT_ID_PATTERN = r"^([1-9]|1\d|2[0-2]|X|Y)-\d+-[ACGT]+-[ACGT]+$"

_DEFAULT_DATASETS = ["gnomad_r4", "gnomad_r3", "gnomad_r2_1"]

# Datasets and their reference build. Only gnomad_r2_1 is GRCh37.
_GRCH37_DATASETS = {"gnomad_r2_1"}

_COMPARE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "variant_id": {"type": "string"},
        "datasets": {"type": "object"},
        "comparison": {
            "type": "object",
            "properties": {
                "overall_af_by_dataset": {"type": "object"},
                "per_population_af_deltas": {"type": "array", "items": {"type": "object"}},
            },
        },
        "build_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["variant_id", "datasets", "comparison"],
    "additionalProperties": True,
}

# gnomAD does not return upstream errors for a build-mismatched coordinate; it
# simply 404s. We treat these as "absent in that dataset" rather than failures.
_ABSENT_EXCEPTIONS = (DataNotFoundError, VariantNotFoundError)
_UPSTREAM_EXCEPTIONS = (GnomadApiError, TimeoutError)


async def _resolve_r2_1_id(
    service: FrequencyService, variant_id: str, *, auto_liftover: bool
) -> tuple[str | None, str]:
    """Return (lifted_grch37_id, note) for the gnomad_r2_1 leg.

    The supplied variant_id is GRCh38 (it passed the autosomal grammar and the
    caller is comparing GRCh38 releases). For r2_1 (GRCh37) we must lift it.
    Returns (None, note) when auto_liftover is off or no mapping exists, which
    the caller records as {present: false}.
    """
    if not auto_liftover:
        return None, (
            "gnomad_r2_1 is GRCh37; auto_liftover=False so the GRCh38 id was not "
            "converted and r2_1 was skipped. Call liftover_variant to compare it."
        )
    results = await service.liftover_variant(variant_id, "GRCh38")
    for item in results:
        lifted = (item.get("liftover") or {}).get("variant_id")
        if lifted:
            return lifted, (
                f"gnomad_r2_1 (GRCh37) used lifted id {lifted} from GRCh38 {variant_id}."
            )
    return None, (f"gnomad_r2_1 (GRCh37) skipped: no liftover mapping found for {variant_id}.")


def register_comparison_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="compare_variant_across_datasets",
        title="Compare One Variant Across gnomAD Datasets",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=relax_output_schema(_COMPARE_OUTPUT_SCHEMA),
        tags={"variant"},
    )
    async def compare_variant_across_datasets(
        variant_id: Annotated[
            str,
            Field(
                description="GRCh38 CHROM-POS-REF-ALT id (e.g. 1-55039974-G-T). r2_1 is auto-lifted to GRCh37.",
                min_length=5,
                max_length=200,
                pattern=_AUTOSOMAL_VARIANT_ID_PATTERN,
                examples=["1-55039974-G-T", "17-7673803-G-A"],
            ),
        ],
        datasets: Annotated[
            list[Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"]] | None,
            Field(
                description="Datasets to compare. None compares gnomad_r4, gnomad_r3, gnomad_r2_1.",
                examples=[["gnomad_r4", "gnomad_r3", "gnomad_r2_1"]],
            ),
        ] = None,
        populations: Annotated[
            list[str] | None,
            Field(
                description="Restrict per-population rows to these codes (e.g. ['afr','nfe']). None keeps all.",
                examples=[["afr", "nfe"]],
            ),
        ] = None,
        auto_liftover: Annotated[
            bool,
            Field(
                description="Lift the GRCh38 id to GRCh37 for gnomad_r2_1. Off skips r2_1 with a build note.",
            ),
        ] = True,
        response_mode: Annotated[
            Literal["compact", "full"],
            Field(
                description="compact (default) drops the duplicated per-dataset exome/genome "
                "population arrays (~half the payload) since comparison.per_population_af_deltas "
                "already carries every per-population AF; full keeps the raw ac/an rows.",
            ),
        ] = "compact",
    ) -> dict[str, Any]:
        """Use this when a caller wants to see how one variant's allele frequencies shift across gnomAD releases (r4 vs r3 vs r2_1) and which populations diverge most. Datasets that lack the variant are marked present=false (partial success); the GRCh37 gnomad_r2_1 leg is auto-lifted from the GRCh38 id. Pair with get_clinvar_variant_details for clinical context. Compact (default) drops the per-dataset population arrays (comparison.per_population_af_deltas keeps the per-pop AFs); response_mode='full' returns the raw rows. Returns ~2-4kB compact, ~3-8kB full."""

        async def call() -> dict[str, Any]:
            selected = datasets if datasets is not None else list(_DEFAULT_DATASETS)
            service = service_factory()
            per_dataset: dict[str, dict[str, Any]] = {}
            build_notes: list[str] = []
            upstream_failures = 0
            attempted = 0

            for dataset in selected:
                lookup_id = variant_id
                lifted_id: str | None = None
                if dataset in _GRCH37_DATASETS:
                    lifted_id, note = await _resolve_r2_1_id(
                        service, variant_id, auto_liftover=auto_liftover
                    )
                    build_notes.append(note)
                    if lifted_id is None:
                        per_dataset[dataset] = {"present": False}
                        continue
                    lookup_id = lifted_id

                attempted += 1
                try:
                    response = await service.get_variant_frequencies(lookup_id, dataset)
                except _ABSENT_EXCEPTIONS:
                    per_dataset[dataset] = {"present": False}
                    continue
                except _UPSTREAM_EXCEPTIONS:
                    upstream_failures += 1
                    per_dataset[dataset] = {"present": False}
                    continue

                shaped = shape_variant_frequencies(
                    response,
                    populations=populations,
                    include_subcohorts=False,
                    include_sex_split=False,
                    exclude_zero_populations=True,
                )
                entry: dict[str, Any] = {"present": True, **shaped}
                if lifted_id is not None:
                    entry["lifted_variant_id"] = lifted_id
                per_dataset[dataset] = entry

            present_count = sum(1 for e in per_dataset.values() if e.get("present"))
            # Fail the whole call only when every attempted lookup failed for an
            # upstream reason (not simple absence). Pure 404s -> partial success.
            if present_count == 0 and attempted > 0 and upstream_failures == attempted:
                raise GnomadApiError(
                    "All requested datasets failed upstream for "
                    f"{variant_id}; none could be compared."
                )

            # Build deltas from the FULL per-dataset populations first, then (in
            # compact mode) drop those arrays: per_population_af_deltas already
            # carries every per-population AF, so keeping them is pure duplication.
            comparison = build_comparison(per_dataset)
            if response_mode == "compact":
                for entry in per_dataset.values():
                    for src_key in ("exome", "genome"):
                        src = entry.get(src_key)
                        if isinstance(src, dict):
                            src.pop("populations", None)
                            src.pop("truncated", None)
            payload: dict[str, Any] = {
                "headline": comparison_headline(
                    {"variant_id": variant_id, "comparison": comparison}
                ),
                "variant_id": variant_id,
                "datasets": per_dataset,
                "comparison": comparison,
                "build_notes": build_notes,
            }
            if response_mode == "compact":
                payload["populations_note"] = (
                    "Per-dataset population arrays omitted (response_mode=compact); "
                    "per-population AFs are in comparison.per_population_af_deltas. "
                    "Use response_mode='full' for raw ac/an rows."
                )
            payload["_meta"] = {
                "next_commands": [
                    {
                        "tool": "get_clinvar_variant_details",
                        "arguments": {"variant_id": variant_id, "reference_genome": "GRCh38"},
                    },
                    {
                        "tool": "compute_carrier_frequency",
                        # inheritance is REQUIRED (no default) on compute_carrier_frequency;
                        # advertise a concrete AR call so the chained command is valid.
                        "arguments": {
                            "variant_id": variant_id,
                            "inheritance": "AR",
                            "dataset": "gnomad_r4",
                        },
                    },
                ]
            }
            return payload

        return await run_mcp_tool(
            "compare_variant_across_datasets",
            call,
            context=McpErrorContext(
                tool_name="compare_variant_across_datasets", variant_id=variant_id
            ),
        )
