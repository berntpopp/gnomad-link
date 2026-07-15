"""Coverage tool: get_coverage (gene, region, variant read-depth)."""

from __future__ import annotations

import re
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
from gnomad_link.mcp.errors import BuildMismatchError, McpErrorContext, ToolInputError, run_mcp_tool
from gnomad_link.mcp.headline import coverage_headline
from gnomad_link.mcp.shaping import cap_region_span
from gnomad_link.services import FrequencyService

_AUTOSOMAL_VARIANT_ID_PATTERN = r"^([1-9]|1\d|2[0-2]|X|Y)-\d+-[ACGT]+-[ACGT]+$"
_REGION_PATTERN = r"^(chr)?([1-9]|1[0-9]|2[0-2]|X|Y)-\d+-\d+$"
_VARIANT_RE = re.compile(_AUTOSOMAL_VARIANT_ID_PATTERN)
_REGION_RE = re.compile(_REGION_PATTERN)


def _classify_coverage_target(
    target: str,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Auto-detect (gene_symbol, gene_id, region, variant_id) from one target string.

    variant (CHROM-POS-REF-ALT) and region (chr-start-stop) are matched by grammar;
    an ENSG-shaped token is a gene_id; anything else is a gene symbol.
    """
    if _VARIANT_RE.fullmatch(target):
        return None, None, None, target
    if _REGION_RE.fullmatch(target):
        return None, None, target, None
    if target.upper().startswith("ENSG"):
        return None, target, None, None
    return target, None, None, None


def register_coverage_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="get_coverage",
        title="Get Read-Depth Coverage",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=None,
        tags={"coordinates"},
    )
    async def get_coverage(
        target: Annotated[
            str,
            Field(
                description="Gene symbol, Ensembl gene ID (ENSG...), region "
                "(chr-start-stop, span capped at 100kb), or variant (CHROM-POS-REF-ALT) "
                "for scalar per-variant coverage. The scope is auto-detected.",
                examples=["PCSK9"],
            ),
        ],
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
        """Use this when a caller needs gnomAD read-depth coverage for a gene, region, or single variant. Pass ONE target — a gene symbol, Ensembl gene ID, region (chr-start-stop), or variant (CHROM-POS-REF-ALT) — and the scope is auto-detected. Gene/region return per-position bins plus a {mean_coverage, fraction_over_20} summary; variant returns scalar coverage. Compact mode trims each bin and caps bin count. Returns ~3-40kB compact (bin-count dependent), larger with response_mode='full'."""

        gene_symbol, gene_id, region, variant_id = _classify_coverage_target(target)

        async def call() -> dict[str, Any]:
            service = service_factory()

            if region is not None:
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
                next_commands = [
                    {
                        "tool": "get_gene_details",
                        "arguments": {"gene": gene_id or gene_symbol, "dataset": dataset},
                    },
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
            return {"headline": coverage_headline(shaped), **shaped}

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
