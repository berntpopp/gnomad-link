"""Structural variant, mitochondrial variant, and transcript tools."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Annotated, Any, Literal, cast

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool
from gnomad_link.mcp.schema_relax import relax_output_schema
from gnomad_link.mcp.shaping import shape_mitochondrial_variant
from gnomad_link.mcp.sv_shaping import shape_structural_variant
from gnomad_link.models import MitochondrialVariant, StructuralVariant, Transcript
from gnomad_link.services import FrequencyService

# gnomAD SV IDs are <TYPE>_chr<CHROM>_<UID>. TYPE covers the documented SV
# classes (DEL/DUP/INS/INV/BND/CPX/CTX/MCNV). CHROM is 1-22, X, Y, M (no MT).
_SV_ID_PATTERN = r"^(DEL|DUP|INS|INV|BND|CPX|CTX|MCNV)_chr([1-9]|1\d|2[0-2]|X|Y|M)_\w+$"

# Accept canonical `M-` plus `chrM-`, `MT-`, `chrMT-` (case-insensitive) aliases
# at schema validation time; the tool normalizes to canonical `M-` before
# invoking the service.
_MITO_VARIANT_ID_PATTERN = r"^(?:chr)?(?:M|MT|m|mt)-\d+-[ACGTacgt]+-[ACGTacgt]+$"
_MITO_PREFIX_RE = re.compile(r"^(?:chr)?(?:MT?)-", re.IGNORECASE)


def _normalize_mito_variant_id(variant_id: str) -> str:
    """Normalize chrM/MT/chrMT prefixes to canonical M-."""

    return _MITO_PREFIX_RE.sub("M-", variant_id, count=1)


def register_specialty_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="get_structural_variant",
        title="Get Structural Variant",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=relax_output_schema(StructuralVariant.model_json_schema()),
        tags={"variant"},
    )
    async def get_structural_variant(
        variant_id: Annotated[
            str,
            Field(
                description="gnomAD SV identifier (e.g. DEL_chr1_1 or DUP_chr17_5).",
                min_length=3,
                max_length=200,
                pattern=_SV_ID_PATTERN,
                examples=["DEL_chr1_1"],
            ),
        ],
        dataset: Annotated[
            Literal["gnomad_sv_r2_1", "gnomad_sv_r4"],
            Field(examples=["gnomad_sv_r4"]),
        ] = "gnomad_sv_r4",
        response_mode: Annotated[
            Literal["compact", "full"],
            Field(
                description="compact drops heavy age/genotype-quality histograms and the "
                "duplicated flat gene list; full returns the raw payload.",
            ),
        ] = "compact",
    ) -> dict[str, Any]:
        """Use this when a caller has a gnomAD structural variant id (deletions, duplications, inversions, translocations/BND, complex/CPX, MCNV). For SNVs/indels use get_variant_frequencies instead. Compact (default) drops heavy histograms + the duplicated flat gene list and emits a `truncated` block; response_mode='full' returns everything. Returns compact ~2-5kB; full ~10-20kB (histograms + populations)."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            raw = await service.get_structural_variant(variant_id, dataset)
            payload = cast(dict[str, Any], raw.get("structural_variant", raw))
            return shape_structural_variant(payload, response_mode=response_mode)

        return await run_mcp_tool(
            "get_structural_variant",
            call,
            context=McpErrorContext(
                tool_name="get_structural_variant",
                variant_id=variant_id,
                dataset=dataset,
            ),
        )

    @mcp.tool(
        name="get_mitochondrial_variant",
        title="Get Mitochondrial Variant",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=relax_output_schema(MitochondrialVariant.model_json_schema()),
        tags={"variant"},
    )
    async def get_mitochondrial_variant(
        variant_id: Annotated[
            str,
            Field(
                description=(
                    "Mitochondrial variant in M-POS-REF-ALT format. "
                    "Accepts chrM-, MT-, and chrMT- aliases (normalized to M-)."
                ),
                min_length=5,
                max_length=100,
                pattern=_MITO_VARIANT_ID_PATTERN,
                examples=["M-7497-G-A"],
            ),
        ],
        dataset: Annotated[
            Literal["gnomad_r3", "gnomad_r4"],
            Field(
                description="gnomad_r4 (GRCh38, default) or gnomad_r3 (GRCh38); gnomad_r2_1 does not include mitochondrial variants",
                examples=["gnomad_r4"],
            ),
        ] = "gnomad_r4",
        include_heteroplasmy_zeros: Annotated[
            bool,
            Field(description="Keep zero-count bins in heteroplasmy_distribution histograms."),
        ] = False,
    ) -> dict[str, Any]:
        """Use this when a caller has a mitochondrial variant id (M-POS-REF-ALT). Mitochondrial ploidy and heteroplasmy fields are returned; for autosomal variants use get_variant_frequencies. By default zero-count heteroplasmy bins are trimmed and a `truncated.kind=heteroplasmy_zeros` block reports the count; set `include_heteroplasmy_zeros=True` to keep them. Returns ~2-4kB."""

        normalized = _normalize_mito_variant_id(variant_id)

        async def call() -> dict[str, Any]:
            service = service_factory()
            raw = await service.get_mitochondrial_variant(normalized, dataset)
            payload = cast(dict[str, Any], raw.get("mitochondrial_variant", raw))
            return shape_mitochondrial_variant(
                payload, include_heteroplasmy_zeros=include_heteroplasmy_zeros
            )

        return await run_mcp_tool(
            "get_mitochondrial_variant",
            call,
            context=McpErrorContext(
                tool_name="get_mitochondrial_variant",
                variant_id=normalized,
                dataset=dataset,
            ),
        )

    @mcp.tool(
        name="get_transcript_details",
        title="Get Transcript Details",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=relax_output_schema(Transcript.model_json_schema()),
        tags={"coordinates"},
    )
    async def get_transcript_details(
        transcript_id: Annotated[
            str,
            Field(
                description="Ensembl transcript ID (ENST...)",
                min_length=4,
                max_length=80,
                examples=["ENST00000302118"],
            ),
        ],
        reference_genome: Annotated[Literal["GRCh37", "GRCh38"], Field()] = "GRCh38",
    ) -> dict[str, Any]:
        """Use this when a caller has an Ensembl transcript id and needs exon structure or GTEx tissue expression. For gene-level info use get_gene_details. Returns ~5-15kB."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            return await service.get_transcript(transcript_id, reference_genome)

        return await run_mcp_tool(
            "get_transcript_details",
            call,
            context=McpErrorContext(tool_name="get_transcript_details"),
        )
