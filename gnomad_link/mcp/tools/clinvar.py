"""ClinVar tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.clinvar_fencing import fence_clinvar_variant
from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool
from gnomad_link.mcp.shaping import summarize_clinvar_submissions
from gnomad_link.services import FrequencyService

# ClinVar is keyed on CHROM-POS-REF-ALT (autosomes, X, Y, and M/MT). The old
# pattern accepted any non-quote string, so a ClinVar variation id or rsID passed
# validation and 404'd downstream; this rejects non-coordinate ids at the boundary.
_CLINVAR_VARIANT_ID_PATTERN = r"^([1-9]|1\d|2[0-2]|X|Y|MT?)-\d+-[ACGT]+-[ACGT]+$"


def register_clinvar_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="get_clinvar_variant_details",
        title="Get ClinVar Variant",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=None,
        tags={"clinical"},
    )
    async def get_clinvar_variant_details(
        variant_id: Annotated[
            str,
            Field(
                description="CHROM-POS-REF-ALT id (autosomes, X, Y, M/MT), e.g. 7-117559590-ATCT-A. "
                "Match the build to reference_genome (GRCh38 default).",
                min_length=5,
                max_length=200,
                pattern=_CLINVAR_VARIANT_ID_PATTERN,
                examples=["7-117559590-ATCT-A"],
            ),
        ],
        reference_genome: Annotated[
            Literal["GRCh37", "GRCh38"],
            Field(description="Lookup build for the variant id. GRCh38 (default) or GRCh37."),
        ] = "GRCh38",
        submissions_limit: Annotated[
            int,
            Field(ge=1, le=200, description="Cap on submissions[] returned. Default 25."),
        ] = 25,
        response_mode: Annotated[
            Literal["compact", "full"],
            Field(
                description="compact (default) drops the per-submission sha256/retrieved_at "
                "integrity bookkeeping (keeps the fenced condition/submitter text); full "
                "returns the complete fenced provenance."
            ),
        ] = "compact",
    ) -> dict[str, Any]:
        """Use this when a caller needs ClinVar clinical significance, review status, gold stars, or submissions for a single variant id. Complementary to get_variant_frequencies for clinical workflows. compact (default) drops per-submission provenance bookkeeping; response_mode='full' keeps it. Returns ~2-8kB compact, larger with full or a high submissions_limit."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            result = await service.get_clinvar_variant(variant_id, reference_genome)
            # Summary is computed from the FULL submissions list BEFORE truncation
            # so the aggregate is accurate even when the response is capped. It
            # reads only clinical_significance (never a fenced field), so it runs
            # on the raw model dump, not the fenced payload.
            all_submissions = [s.model_dump() for s in result.submissions]
            summary = summarize_clinvar_submissions(all_submissions)
            # v1.1 untrusted-content fencing: conditions[*].name and
            # submitter_name are ClinVar submitter-authored free text, surfaced
            # verbatim. fence_clinvar_variant types both as `untrusted_text`,
            # truncates to submissions_limit, and enforces the v1.1 object/byte
            # ceilings over the EMITTED (capped) submissions only -- so a large
            # upstream record never trips the ceiling when the response it
            # actually returns is small.
            payload = fence_clinvar_variant(
                result, submissions_limit=submissions_limit, response_mode=response_mode
            )
            payload["summary"] = summary
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
        output_schema=None,
        tags={"clinical"},
    )
    async def get_clinvar_meta() -> dict[str, Any]:
        """Use this when a caller only needs the ClinVar release date or revision currently served by gnomAD -- cheaper than full capabilities. Returns <1kB. DEPRECATED: prefer get_server_capabilities."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            result = await service.get_clinvar_meta()
            # FrequencyService.get_clinvar_meta is typed dict[str, Any]; merge
            # deprecation hints into any pre-existing _meta keys.
            existing_meta: dict[str, Any] = result.get("_meta") or {}
            result["_meta"] = {
                **existing_meta,
                "deprecated": True,
                "use_instead": "get_server_capabilities",
                "removal_release": "next minor",
            }
            return result

        return await run_mcp_tool(
            "get_clinvar_meta",
            call,
            context=McpErrorContext(tool_name="get_clinvar_meta"),
        )
