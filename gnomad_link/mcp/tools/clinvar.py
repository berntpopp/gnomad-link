"""ClinVar tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool
from gnomad_link.mcp.shaping import shape_clinvar_submissions, summarize_clinvar_submissions
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
        tags={"clinical"},
    )
    async def get_clinvar_variant_details(
        variant_id: Annotated[
            str,
            Field(
                min_length=5,
                max_length=200,
                pattern=r"^[^'\"]+$",
                examples=["1-55051215-G-GA"],
            ),
        ],
        reference_genome: Annotated[Literal["GRCh37", "GRCh38"], Field()] = "GRCh38",
        submissions_limit: Annotated[
            int,
            Field(ge=1, le=200, description="Cap on submissions[] returned. Default 25."),
        ] = 25,
    ) -> dict[str, Any]:
        """Use this when a caller needs ClinVar clinical significance, review status, gold stars, or submissions for a single variant id. Complementary to get_variant_frequencies for clinical workflows. Returns ~3-15kB (submissions_limit dependent)."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            result = await service.get_clinvar_variant(variant_id, reference_genome)
            payload = result.model_dump()
            # Summary is computed from the FULL submissions list BEFORE truncation
            # so the aggregate is accurate even when the response is capped.
            all_submissions = payload.get("submissions") or []
            payload["summary"] = summarize_clinvar_submissions(all_submissions)
            payload = shape_clinvar_submissions(payload, submissions_limit=submissions_limit)
            # Suggest pairing with frequency data using the same variant_id.
            existing_meta: dict[str, Any] = payload.get("_meta") or {}
            existing_next: list[Any] = existing_meta.get("next_commands", [])
            freq_cmd: dict[str, Any] = {
                "tool": "get_variant_frequencies",
                "arguments": {"variant_id": variant_id},
            }
            payload["_meta"] = {
                **existing_meta,
                "next_commands": [*existing_next, freq_cmd],
            }
            return payload

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
        tags={"clinical"},
    )
    async def get_clinvar_meta() -> dict[str, Any]:
        """Use this when a caller only needs the ClinVar release date or revision currently served by gnomAD -- cheaper than full capabilities. Returns <1kB."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            return await service.get_clinvar_meta()

        return await run_mcp_tool(
            "get_clinvar_meta",
            call,
            context=McpErrorContext(tool_name="get_clinvar_meta"),
        )
