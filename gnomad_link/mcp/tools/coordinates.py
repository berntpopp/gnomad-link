"""Liftover and region tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal, cast

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.build_check import detect_region_mismatch
from gnomad_link.mcp.errors import BuildMismatchError, McpErrorContext, ToolInputError, run_mcp_tool
from gnomad_link.mcp.schema_relax import relax_output_schema
from gnomad_link.mcp.shaping import cap_region_span, shape_region_payload
from gnomad_link.models import LiftoverResponse, Region
from gnomad_link.services import FrequencyService

_REGION_PATTERN = r"^(chr)?([1-9]|1[0-9]|2[0-2]|X|Y|M|MT)-\d+-\d+$"

# Liftover accepts mito too — converting M-... between builds is a valid call.
_LIFTOVER_VARIANT_ID_PATTERN = r"^([1-9]|1\d|2[0-2]|X|Y|MT?)-\d+-[ACGT]+-[ACGT]+$"


def register_coordinate_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="liftover_variant",
        title="Liftover Variant Between GRCh37 and GRCh38",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=relax_output_schema(LiftoverResponse.model_json_schema()),
        tags={"coordinates"},
    )
    async def liftover_variant(
        source_variant_id: Annotated[
            str,
            Field(
                description="Variant ID to convert (CHROM-POS-REF-ALT). Mitochondrial M/MT prefixes are accepted.",
                min_length=5,
                max_length=200,
                pattern=_LIFTOVER_VARIANT_ID_PATTERN,
                examples=["1-55051215-G-GA", "MT-7497-G-A"],
            ),
        ],
        source_genome: Annotated[
            Literal["GRCh37", "GRCh38"] | None,
            Field(
                description="Reference build of source_variant_id. Preferred name.",
            ),
        ] = None,
        reference_genome: Annotated[
            Literal["GRCh37", "GRCh38"] | None,
            Field(
                description="Deprecated alias for source_genome; will be removed in the next release.",
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Use this when a caller has a variant id in one reference build and needs the equivalent id in the other. Works BOTH directions (GRCh37<->GRCh38); the converted coordinate is in each result's `target_variant_id` (and `target_reference_genome` names the build). Use this BEFORE calling frequency tools if the dataset and coordinate build do not match. Prefer source_genome; reference_genome is a deprecated alias. Returns <1kB."""

        async def call() -> dict[str, Any]:
            build = source_genome or reference_genome
            if build is None:
                raise ToolInputError(
                    "Provide source_genome (or legacy reference_genome) to indicate "
                    "the build of source_variant_id."
                )
            service = service_factory()
            results = await service.liftover_variant(source_variant_id, build)
            target = "GRCh38" if build == "GRCh37" else "GRCh37"
            # Each gnomAD record carries BOTH the GRCh37 `source` and GRCh38
            # `liftover` coordinate; surface the one in the target build directly
            # so the LLM does not have to know which field to read per direction.
            for record in results:
                for key in ("source", "liftover"):
                    entry = record.get(key) or {}
                    if entry.get("reference_genome") == target:
                        record["target_variant_id"] = entry.get("variant_id")
            payload: dict[str, Any] = {
                "results": results,
                "source_variant_id": source_variant_id,
                "source_reference_genome": build,
                "target_reference_genome": target,
                "query_type": "forward" if build == "GRCh37" else "reverse",
            }
            if not results:
                # An empty result is a valid answer, not an error: explain it so the
                # LLM does not read bare results:[] as a failure (mirrors how
                # compare_variant_across_datasets surfaces build_notes).
                payload["build_note"] = (
                    f"No liftover mapping found for {source_variant_id} from {build} to "
                    f"{target}. The variant may be build-specific (no equivalent coordinate "
                    "in the other genome), an indel that does not lift cleanly, or absent "
                    "from the liftover tables. Confirm the id with resolve_variant_id."
                )
            meta: dict[str, Any] = {}
            if source_genome is None and reference_genome is not None:
                meta["deprecated_params"] = {
                    "reference_genome": (
                        "Use source_genome; reference_genome will be removed in the next release."
                    )
                }
            # Close the build-conversion loop: chain the converted coordinate
            # straight into a frequency lookup against the build-correct dataset.
            target_id = next(
                (r.get("target_variant_id") for r in results if r.get("target_variant_id")),
                None,
            )
            if target_id:
                target_dataset = "gnomad_r4" if target == "GRCh38" else "gnomad_r2_1"
                meta["next_commands"] = [
                    {
                        "tool": "get_variant_frequencies",
                        "arguments": {"variant_id": target_id, "dataset": target_dataset},
                    }
                ]
            if meta:
                payload["_meta"] = meta
            return payload

        return await run_mcp_tool(
            "liftover_variant",
            call,
            context=McpErrorContext(tool_name="liftover_variant", variant_id=source_variant_id),
        )

    @mcp.tool(
        name="get_region",
        title="Get Variants and Genes in a Region",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=relax_output_schema(Region.model_json_schema()),
        tags={"coordinates"},
    )
    async def get_region(
        region: Annotated[
            str,
            Field(
                description="Region in chr-start-stop format (e.g. 17-7674232-7674252).",
                pattern=_REGION_PATTERN,
            ),
        ],
        dataset: Annotated[
            Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"],
            Field(
                description="gnomad_r4 (GRCh38, default, largest cohort), gnomad_r3 (GRCh38, whole-genome), gnomad_r2_1 (GRCh37 legacy)",
                examples=["gnomad_r4"],
            ),
        ] = "gnomad_r4",
        include_clinvar: Annotated[
            bool,
            Field(description="Include ClinVar variants in the region."),
        ] = True,
        include_genes: Annotated[
            bool,
            Field(description="Include overlapping genes."),
        ] = True,
        max_clinvar_variants: Annotated[
            int,
            Field(
                ge=1,
                le=2000,
                description="Cap on clinvar_variants[] returned. Default 100.",
            ),
        ] = 100,
        max_genes: Annotated[
            int,
            Field(
                ge=1,
                le=500,
                description="Cap on genes[] returned. Default 50.",
            ),
        ] = 50,
        compact_rows: Annotated[
            bool,
            Field(description="Project clinvar/gene rows to a compact key set."),
        ] = True,
    ) -> dict[str, Any]:
        """Use this when a caller wants genes and/or ClinVar variants in a small region (<=100kb). Spans larger than 100kb are clamped and a `truncated` block reports it. Per-category caps (`max_clinvar_variants`, `max_genes`) keep payload bounded; surplus rows are summarised in a `truncated_payload` block. For per-variant SNV listings use get_gene_variants instead. Returns ~5-30kB at compact defaults; up to ~50kB with compact_rows=False."""

        async def call() -> dict[str, Any]:
            chrom, start_s, stop_s = region.removeprefix("chr").split("-")
            start, stop = int(start_s), int(stop_s)
            if stop <= start:
                raise ToolInputError("Region stop must be greater than start.")
            inferred = detect_region_mismatch(chrom, start, dataset)
            if inferred is not None:
                raise BuildMismatchError(
                    variant_id=f"{chrom}-{start}-{stop}",
                    inferred_build=inferred,
                    dataset=dataset,
                )
            adj_start, adj_stop, capped = cap_region_span(chrom, start, stop)
            service = service_factory()
            raw = await service.get_region(chrom, adj_start, adj_stop, dataset)
            payload = cast(dict[str, Any], raw.get("region", raw))
            payload = shape_region_payload(
                payload,
                include_clinvar=include_clinvar,
                include_genes=include_genes,
                max_clinvar_variants=max_clinvar_variants,
                max_genes=max_genes,
                compact_rows=compact_rows,
            )
            if capped:
                payload["truncated"] = {
                    "kind": "region_span",
                    "requested_bp": stop - start,
                    "served_bp": adj_stop - adj_start,
                    "to_disable": "request smaller windows; max 100kb per call",
                }
            # Chain the first gene/ClinVar hit into the natural drill-down tools.
            next_cmds: list[dict[str, Any]] = []
            genes = payload.get("genes") or []
            if genes and genes[0].get("gene_id"):
                next_cmds.append(
                    {
                        "tool": "get_gene_variants",
                        "arguments": {"gene_id": genes[0]["gene_id"], "dataset": dataset},
                    }
                )
            clinvars = payload.get("clinvar_variants") or []
            if clinvars and clinvars[0].get("variant_id"):
                region_build = "GRCh37" if dataset == "gnomad_r2_1" else "GRCh38"
                next_cmds.append(
                    {
                        "tool": "get_clinvar_variant_details",
                        "arguments": {
                            "variant_id": clinvars[0]["variant_id"],
                            "reference_genome": region_build,
                        },
                    }
                )
            if next_cmds:
                payload.setdefault("_meta", {})["next_commands"] = next_cmds
            return payload

        return await run_mcp_tool(
            "get_region",
            call,
            context=McpErrorContext(tool_name="get_region", region=region, dataset=dataset),
        )
