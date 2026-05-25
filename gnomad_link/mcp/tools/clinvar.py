"""ClinVar tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool
from gnomad_link.models import ClinVarVariant
from gnomad_link.services import FrequencyService


def register_clinvar_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="get_clinvar_variant_details",
        title="Get ClinVar Variant",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=ClinVarVariant.model_json_schema(),
    )
    async def get_clinvar_variant_details(
        variant_id: Annotated[
            str,
            Field(min_length=5, max_length=200, pattern=r"^[^'\"]+$"),
        ],
        reference_genome: Annotated[Literal["GRCh37", "GRCh38"], Field()] = "GRCh38",
    ) -> dict[str, Any]:
        """Use this when a caller needs ClinVar clinical significance, review status, gold stars, or submissions for a single variant id. Complementary to get_variant_frequencies for clinical workflows."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            result = await service.get_clinvar_variant(variant_id, reference_genome)
            return result.model_dump()

        return await run_mcp_tool(
            "get_clinvar_variant_details",
            call,
            context=McpErrorContext(tool_name="get_clinvar_variant_details", variant_id=variant_id),
        )

    @mcp.tool(
        name="get_clinvar_meta",
        title="Get ClinVar Metadata",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema={"type": "object", "additionalProperties": True},
    )
    async def get_clinvar_meta() -> dict[str, Any]:
        """Use this when a caller only needs the ClinVar release date or revision currently served by gnomAD -- cheaper than full capabilities."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            return await service.get_clinvar_meta()

        return await run_mcp_tool(
            "get_clinvar_meta",
            call,
            context=McpErrorContext(tool_name="get_clinvar_meta"),
        )
