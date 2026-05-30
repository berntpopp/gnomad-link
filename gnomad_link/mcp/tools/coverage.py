"""Coverage tool: get_coverage (gene, region, variant read-depth)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.build_check import (
    detect_region_mismatch,
    detect_variant_id_mismatch,
)
from gnomad_link.mcp.coverage_shaping import shape_coverage_payload
from gnomad_link.mcp.errors import BuildMismatchError, McpErrorContext, run_mcp_tool
from gnomad_link.mcp.schema_relax import relax_output_schema
from gnomad_link.mcp.shaping import cap_region_span
from gnomad_link.services import FrequencyService

_AUTOSOMAL_VARIANT_ID_PATTERN = r"^([1-9]|1\d|2[0-2]|X|Y)-\d+-[ACGT]+-[ACGT]+$"
_GENE_ID_PATTERN = r"^ENSG\d{11}$"
_GENE_SYMBOL_PATTERN = r"^[A-Za-z0-9._-]{1,32}$"
_REGION_PATTERN = r"^(chr)?([1-9]|1[0-9]|2[0-2]|X|Y)-\d+-\d+$"

_COVERAGE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "scope": {"type": "string"},
        "identity": {"type": "object"},
        "dataset": {"type": "string"},
        "exome": {"type": ["object", "null"]},
        "genome": {"type": ["object", "null"]},
    },
    "required": ["scope", "dataset"],
    "additionalProperties": True,
}


def register_coverage_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="get_coverage",
        title="Get Read-Depth Coverage",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=relax_output_schema(_COVERAGE_OUTPUT_SCHEMA),
        tags={"coordinates"},
    )
    async def get_coverage(
        gene_symbol: Annotated[
            str | None,
            Field(
                default=None,
                description="HGNC gene symbol (e.g. PCSK9). One scope arg only.",
                pattern=_GENE_SYMBOL_PATTERN,
                examples=["PCSK9"],
            ),
        ] = None,
        gene_id: Annotated[
            str | None,
            Field(
                default=None,
                description="Ensembl gene ID (ENSG...). One scope arg only.",
                pattern=_GENE_ID_PATTERN,
                examples=["ENSG00000169174"],
            ),
        ] = None,
        region: Annotated[
            str | None,
            Field(
                default=None,
                description="chr-start-stop (e.g. 1-55039447-55064852). Span capped at 100kb. One scope arg only.",
                pattern=_REGION_PATTERN,
                examples=["1-55039447-55064852"],
            ),
        ] = None,
        variant_id: Annotated[
            str | None,
            Field(
                default=None,
                description="CHROM-POS-REF-ALT for scalar per-variant coverage. One scope arg only.",
                pattern=_AUTOSOMAL_VARIANT_ID_PATTERN,
                examples=["1-55039447-A-G"],
            ),
        ] = None,
        dataset: Annotated[
            Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"],
            Field(
                description="gnomad_r4 (GRCh38, default), gnomad_r3 (GRCh38), gnomad_r2_1 (GRCh37 legacy)",
                examples=["gnomad_r4"],
            ),
        ] = "gnomad_r4",
        response_mode: Annotated[
            Literal["compact", "full"],
            Field(
                description="compact trims each bin to pos/mean/median/over_20/over_30; full keeps all over_* thresholds."
            ),
        ] = "compact",
        max_bins: Annotated[
            int,
            Field(
                ge=1,
                le=20_000,
                description="Cap on coverage bins per source (gene/region). Summary still reflects all bins.",
            ),
        ] = 2_000,
    ) -> dict[str, Any]:
        """Use this when a caller needs gnomAD read-depth coverage for a gene, region, or single variant. Provide exactly ONE of gene_symbol, gene_id, region, or variant_id. Gene/region return per-position bins plus a {mean_coverage, fraction_over_20} summary; variant returns scalar coverage. Compact mode trims each bin and caps bin count. Returns ~3-40kB compact (bin-count dependent), larger with response_mode='full'."""

        provided = [
            ("gene_symbol", gene_symbol),
            ("gene_id", gene_id),
            ("region", region),
            ("variant_id", variant_id),
        ]
        set_args = [name for name, value in provided if value]

        async def call() -> dict[str, Any]:
            if len(set_args) != 1:
                raise ValueError(
                    "Provide exactly one of gene_symbol, gene_id, region, or variant_id "
                    f"(got {len(set_args)}: {set_args})."
                )
            service = service_factory()

            if region is not None:
                chrom, start_s, stop_s = region.removeprefix("chr").split("-")
                start, stop = int(start_s), int(stop_s)
                if stop <= start:
                    raise ValueError("Region stop must be greater than start.")
                inferred = detect_region_mismatch(chrom, start, dataset)
                if inferred is not None:
                    raise BuildMismatchError(
                        variant_id=f"{chrom}-{start}-{stop}",
                        inferred_build=inferred,
                        dataset=dataset,
                    )
                adj_start, adj_stop, _capped = cap_region_span(chrom, start, stop)
                raw = await service.get_coverage(
                    scope="region",
                    dataset=dataset,
                    chrom=chrom,
                    start=adj_start,
                    stop=adj_stop,
                )
                scope = "region"
                next_commands = [
                    {"tool": "get_region", "arguments": {"region": region, "dataset": dataset}},
                ]
            elif variant_id is not None:
                inferred = detect_variant_id_mismatch(variant_id, dataset)
                if inferred is not None:
                    raise BuildMismatchError(
                        variant_id=variant_id, inferred_build=inferred, dataset=dataset
                    )
                raw = await service.get_coverage(
                    scope="variant", dataset=dataset, variant_id=variant_id
                )
                scope = "variant"
                next_commands = [
                    {
                        "tool": "get_variant_frequencies",
                        "arguments": {"variant_id": variant_id, "dataset": dataset},
                    },
                ]
            else:  # gene_symbol or gene_id
                raw = await service.get_coverage(
                    scope="gene",
                    dataset=dataset,
                    gene_id=gene_id,
                    gene_symbol=gene_symbol,
                )
                scope = "gene"
                gene_args: dict[str, Any] = {"dataset": dataset}
                if gene_symbol:
                    gene_args["gene_symbol"] = gene_symbol
                if gene_id:
                    gene_args["gene_id"] = gene_id
                next_commands = [
                    {"tool": "get_gene_details", "arguments": gene_args},
                ]

            shaped = shape_coverage_payload(
                raw,
                scope=scope,
                dataset=dataset,
                response_mode=response_mode,
                max_bins=max_bins,
            )
            existing_meta: dict[str, Any] = shaped.get("_meta") or {}
            existing_next: list[Any] = existing_meta.get("next_commands", [])
            shaped["_meta"] = {
                **existing_meta,
                "next_commands": [*existing_next, *next_commands],
            }
            return shaped

        return await run_mcp_tool(
            "get_coverage",
            call,
            context=McpErrorContext(
                tool_name="get_coverage",
                gene_id=gene_id,
                gene_symbol=gene_symbol,
                region=region,
                variant_id=variant_id,
                dataset=dataset,
            ),
        )
