"""Structural variant, mitochondrial variant, and transcript tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool
from gnomad_link.models import MitochondrialVariant, StructuralVariant, Transcript
from gnomad_link.services import FrequencyService


def register_specialty_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="get_structural_variant",
        title="Get Structural Variant",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=StructuralVariant.model_json_schema(),
    )
    async def get_structural_variant(
        variant_id: Annotated[
            str,
            Field(
                description="gnomAD SV identifier.",
                min_length=3,
                max_length=200,
            ),
        ],
        dataset: Annotated[Literal["gnomad_sv_r2_1", "gnomad_sv_r4"], Field()] = "gnomad_sv_r4",
    ) -> dict[str, Any]:
        """Use this when a caller has a gnomAD structural variant id (deletions, duplications, inversions, BNDs). For SNVs/indels use get_variant_frequencies instead."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            raw = await service.get_structural_variant(variant_id, dataset)
            return raw.get("structural_variant", raw) if isinstance(raw, dict) else raw

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
        output_schema=MitochondrialVariant.model_json_schema(),
    )
    async def get_mitochondrial_variant(
        variant_id: Annotated[
            str,
            Field(
                description="Mitochondrial variant in M-POS-REF-ALT format.",
                min_length=5,
                max_length=100,
            ),
        ],
        dataset: Annotated[Literal["gnomad_r3", "gnomad_r4"], Field()] = "gnomad_r4",
    ) -> dict[str, Any]:
        """Use this when a caller has a mitochondrial variant id (M-POS-REF-ALT). Mitochondrial ploidy and heteroplasmy fields are returned; for autosomal variants use get_variant_frequencies."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            raw = await service.get_mitochondrial_variant(variant_id, dataset)
            return raw.get("mitochondrial_variant", raw) if isinstance(raw, dict) else raw

        return await run_mcp_tool(
            "get_mitochondrial_variant",
            call,
            context=McpErrorContext(
                tool_name="get_mitochondrial_variant",
                variant_id=variant_id,
                dataset=dataset,
            ),
        )

    @mcp.tool(
        name="get_transcript_details",
        title="Get Transcript Details",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=Transcript.model_json_schema(),
    )
    async def get_transcript_details(
        transcript_id: Annotated[
            str,
            Field(
                description="Ensembl transcript ID (ENST...)",
                min_length=4,
                max_length=80,
            ),
        ],
        reference_genome: Annotated[Literal["GRCh37", "GRCh38"], Field()] = "GRCh38",
    ) -> dict[str, Any]:
        """Use this when a caller has an Ensembl transcript id and needs exon structure or GTEx tissue expression. For gene-level info use get_gene_details."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            return await service.get_transcript(transcript_id, reference_genome)

        return await run_mcp_tool(
            "get_transcript_details",
            call,
            context=McpErrorContext(tool_name="get_transcript_details"),
        )
