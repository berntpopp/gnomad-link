from __future__ import annotations

import re
from typing import Any

import pytest

ANTHROPIC_TOOL_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

EXPECTED_TOOLS = {
    "get_server_capabilities",
    "get_variant_frequencies",
    "get_variant_details",
    "get_gene_details",
    "get_gene_variants",
    "get_gene_summary",
    "get_clinvar_variant_details",
    "get_clinvar_meta",
    "compute_variant_liftover",
    "get_structural_variant",
    "get_mitochondrial_variant",
    "get_region",
    "get_transcript_details",
    "search_genes",
    "resolve_variant_id",
    "search_variants",  # deprecated alias retained for one release
    "compute_carrier_frequency",
    "compute_gene_carrier_frequency",
    "get_diagnostics",
    "compare_variant_across_datasets",
    "search_structural_variants",
    "get_coverage",
}

EXPECTED_DATA_TOOLS = EXPECTED_TOOLS - {"get_server_capabilities", "get_diagnostics"}

EXPECTED_RESOURCE_URIS = {
    "gnomad://capabilities",
    "gnomad://usage",
    "gnomad://research-use",
    "gnomad://reference",
    "gnomad://citations",
}


@pytest.mark.asyncio
async def test_create_gnomad_mcp_exposes_expected_tool_names(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    tool_names = {tool.name for tool in await mcp.list_tools()}

    assert tool_names >= EXPECTED_TOOLS
    assert "clear_cache" not in tool_names
    assert "get_structural_variants" not in tool_names
    assert "get_variant_frequency_data" not in tool_names


@pytest.mark.asyncio
async def test_all_tool_names_match_anthropic_remote_mcp_regex(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    offenders = [
        tool.name
        for tool in await mcp.list_tools()
        if not ANTHROPIC_TOOL_NAME_RE.fullmatch(tool.name)
    ]

    assert offenders == []


@pytest.mark.asyncio
async def test_every_data_tool_has_read_only_open_world_annotations(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    tools_by_name = {tool.name: tool for tool in await mcp.list_tools()}

    for name in EXPECTED_DATA_TOOLS:
        ann = tools_by_name[name].annotations
        assert ann is not None, f"{name} missing annotations"
        assert ann.readOnlyHint is True, f"{name} not read-only"
        assert ann.destructiveHint is False, f"{name} marked destructive"
        assert ann.idempotentHint is True, f"{name} not idempotent"
        assert ann.openWorldHint is True, f"{name} should be open-world"


@pytest.mark.asyncio
async def test_capabilities_tool_is_open_world(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    tools_by_name = {tool.name: tool for tool in await mcp.list_tools()}
    ann = tools_by_name["get_server_capabilities"].annotations

    assert ann is not None
    assert ann.openWorldHint is True


@pytest.mark.asyncio
async def test_every_data_tool_advertises_output_schema(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    tools_by_name = {tool.name: tool for tool in await mcp.list_tools()}

    for name in EXPECTED_DATA_TOOLS:
        schema = tools_by_name[name].output_schema
        assert schema is not None, f"{name} missing output_schema"
        assert isinstance(schema, dict)


@pytest.mark.asyncio
async def test_every_tool_description_leads_with_use_this_when(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    offenders = [
        tool.name
        for tool in await mcp.list_tools()
        if not (tool.description or "").lstrip().lower().startswith("use this when")
    ]
    assert offenders == [], f"tools missing LLM-routing description: {offenders}"


def test_server_instructions_include_workflows_and_safety(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    instructions = create_gnomad_mcp(service_factory=fake_service_factory).instructions or ""

    assert "Variant frequency" in instructions
    assert "get_server_capabilities" in instructions
    assert "gnomad://capabilities" in instructions
    assert "Research use only" in instructions
    assert len(instructions) < 1400


@pytest.mark.asyncio
async def test_capabilities_resources_are_registered(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    resource_uris = {str(res.uri) for res in await mcp.list_resources()}
    assert resource_uris >= EXPECTED_RESOURCE_URIS


@pytest.mark.asyncio
async def test_json_resources_advertise_application_json(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    resources = {str(res.uri): res for res in await mcp.list_resources()}

    for uri in {
        "gnomad://capabilities",
        "gnomad://research-use",
        "gnomad://reference",
        "gnomad://citations",
    }:
        assert resources[uri].mime_type == "application/json"


@pytest.mark.asyncio
async def test_get_diagnostics_returns_health_and_recent_errors(
    fake_service_factory,
) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    tools_by_name = {tool.name: tool for tool in await mcp.list_tools()}
    assert "get_diagnostics" in tools_by_name
    tool = tools_by_name["get_diagnostics"]
    # Must be closed-world (local health data, no upstream call)
    assert tool.annotations is not None
    assert tool.annotations.openWorldHint is False


@pytest.mark.asyncio
async def test_diagnostics_tool_is_closed_world(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    tools_by_name = {tool.name: tool for tool in await mcp.list_tools()}
    ann = tools_by_name["get_diagnostics"].annotations
    assert ann is not None
    assert ann.openWorldHint is False
    assert ann.readOnlyHint is True


@pytest.mark.asyncio
async def test_workflow_prompts_registered(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    prompts = await mcp.list_prompts()
    prompt_names = {p.name for p in prompts}
    assert "variant_frequency_workflow" in prompt_names
    assert "gene_constraint_workflow" in prompt_names
    assert "clinical_variant_workflow" in prompt_names
    assert "region_scan_workflow" in prompt_names


@pytest.mark.asyncio
async def test_workflow_prompt_args_advertise_tool_patterns(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp
    from gnomad_link.mcp.patterns import GENE_SYMBOL_PATTERN
    from gnomad_link.mcp.tools.clinvar import _CLINVAR_VARIANT_ID_PATTERN
    from gnomad_link.mcp.tools.coordinates import _REGION_PATTERN
    from gnomad_link.mcp.tools.variants import _AUTOSOMAL_VARIANT_ID_PATTERN

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    prompts = {prompt.name: prompt for prompt in await mcp.list_prompts()}

    expected = {
        "variant_frequency_workflow": _AUTOSOMAL_VARIANT_ID_PATTERN,
        "gene_constraint_workflow": GENE_SYMBOL_PATTERN,
        "clinical_variant_workflow": _CLINVAR_VARIANT_ID_PATTERN,
        "region_scan_workflow": _REGION_PATTERN,
    }
    for prompt_name, pattern in expected.items():
        arguments = prompts[prompt_name].arguments
        assert arguments is not None
        assert pattern in (arguments[0].description or "")


@pytest.mark.asyncio
async def test_workflow_prompt_args_are_pattern_validated(fake_service_factory) -> None:
    from fastmcp.exceptions import PromptError

    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)

    await mcp.render_prompt("variant_frequency_workflow", {"variant_id": "1-55051215-G-GA"})
    await mcp.render_prompt("gene_constraint_workflow", {"gene_symbol": "PCSK9"})
    await mcp.render_prompt("clinical_variant_workflow", {"variant_id": "MT-7497-G-A"})
    await mcp.render_prompt("region_scan_workflow", {"region": "MT-1-200"})

    with pytest.raises(PromptError):
        await mcp.render_prompt("variant_frequency_workflow", {"variant_id": "not-a-variant"})


@pytest.mark.asyncio
async def test_capabilities_includes_llm_driver_contract(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp
    from gnomad_link.mcp.resources import get_capabilities_resource

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    _ = mcp  # trigger registration
    caps = get_capabilities_resource()
    assert "llm_driver_contract" in caps
    assert "core_workflow_tools" in caps["llm_driver_contract"]
    assert "output_cheatsheet" in caps
    assert "tool_categories" in caps


@pytest.mark.asyncio
async def test_research_use_resource_registered(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    resource_uris = {str(res.uri) for res in await mcp.list_resources()}
    assert "gnomad://research-use" in resource_uris


@pytest.mark.asyncio
async def test_data_tools_have_category_tags(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    tools_by_name = {tool.name: tool for tool in await mcp.list_tools()}
    # Spot-check a sample of tools for tags
    assert tools_by_name["get_variant_frequencies"].tags == {"variant"}
    assert tools_by_name["get_gene_details"].tags == {"gene"}
    assert tools_by_name["get_clinvar_variant_details"].tags == {"clinical"}
    assert tools_by_name["compute_variant_liftover"].tags == {"coordinates"}
    assert tools_by_name["get_diagnostics"].tags == {"metadata", "diagnostics"}


def test_capabilities_resource_lists_token_cost_hints() -> None:
    from gnomad_link.mcp.resources import get_capabilities_resource

    caps = get_capabilities_resource()
    hints = caps.get("token_cost_hints")
    assert isinstance(hints, dict)
    # Every advertised tool has an entry.
    for tool_name in caps["tools"]:
        assert tool_name in hints, f"missing token_cost_hint for {tool_name}"
        assert isinstance(hints[tool_name], str)
        assert len(hints[tool_name]) <= 80


def test_capabilities_protocol_version_tracks_mcp_sdk() -> None:
    from gnomad_link.mcp.resources import MCP_PROTOCOL_VERSION
    from mcp.types import LATEST_PROTOCOL_VERSION

    assert MCP_PROTOCOL_VERSION == LATEST_PROTOCOL_VERSION


@pytest.mark.asyncio
async def test_capabilities_tools_match_facade_tools(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp
    from gnomad_link.mcp.resources import get_capabilities_resource

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    registered = {tool.name for tool in await mcp.list_tools()}
    caps = get_capabilities_resource()
    advertised = set(caps["tools"])
    assert advertised == registered, (
        f"Capabilities tools list drifted from registered facade tools. "
        f"Only in caps: {advertised - registered}. "
        f"Only registered: {registered - advertised}."
    )


def test_capabilities_includes_clinvar_release_date() -> None:
    from gnomad_link.mcp.resources import get_capabilities_resource

    caps = get_capabilities_resource()
    # Key must be present, value may be None until a startup probe lands.
    assert "clinvar_release_date" in caps
    # gnomad_release already added in B2; keep this assertion for completeness.
    assert "gnomad_release" in caps


def test_capabilities_deprecated_tools_includes_get_clinvar_meta() -> None:
    from gnomad_link.mcp.resources import get_capabilities_resource

    caps = get_capabilities_resource()
    assert "get_clinvar_meta" in caps["deprecated_tools"]


def test_capabilities_documents_prompts() -> None:
    from gnomad_link.mcp.resources import get_capabilities_resource

    caps = get_capabilities_resource()
    assert set(caps["prompts"]) == {
        "variant_frequency_workflow",
        "gene_constraint_workflow",
        "clinical_variant_workflow",
        "region_scan_workflow",
    }


def test_capabilities_lists_full_error_code_set() -> None:
    from gnomad_link.mcp.resources import get_capabilities_resource

    caps = get_capabilities_resource()
    assert set(caps["error_codes"]) == {
        "not_found",
        "invalid_input",
        "build_mismatch",
        "rate_limited",
        "validation_failed",
        "upstream_unavailable",
        "output_validation_failed",
        "internal_error",
    }


def test_capabilities_documents_parameter_conventions_and_contracts() -> None:
    from gnomad_link.mcp.resources import get_capabilities_resource

    caps = get_capabilities_resource()
    assert {"dataset", "reference_genome", "sv_dataset", "liftover"} <= set(
        caps["parameter_conventions"]
    )
    assert caps["contracts"]["resource"] == "gnomad://reference"
    assert caps["concurrency"]["queue_wait_seconds"] >= 1
    assert "af_source" in caps["response_fields"]
    assert "overall_af_source" in caps["response_fields"]["af_source"]


def test_reference_resource_has_taxonomy_truncation_glossary() -> None:
    from gnomad_link.mcp.resources import get_reference_resource

    ref = get_reference_resource()
    # All 8 error codes documented with retryable + when.
    assert set(ref["error_taxonomy"]["codes"]) == {
        "not_found",
        "invalid_input",
        "build_mismatch",
        "rate_limited",
        "validation_failed",
        "upstream_unavailable",
        "output_validation_failed",
        "internal_error",
    }
    # All 14 truncation kinds enumerated, including both SV singular/plural.
    kinds = set(ref["truncation_contract"]["kinds"])
    assert {"structural_variant", "structural_variants"} <= kinds
    assert len(kinds) == 14
    # Field glossary states units/scale for the load-bearing fields.
    assert "ac / an" in ref["field_glossary"]["af"]


@pytest.mark.asyncio
async def test_reference_resource_registered(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    resource_uris = {str(res.uri) for res in await mcp.list_resources()}
    assert "gnomad://reference" in resource_uris


@pytest.mark.asyncio
async def test_get_clinvar_meta_marks_deprecated() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    class _StubMetaService:
        async def get_clinvar_meta(self) -> dict[str, object]:
            return {"clinvar_release_date": "2024-10-15"}

    def service_factory() -> Any:
        return _StubMetaService()

    mcp = create_gnomad_mcp(service_factory=service_factory)
    result = await mcp.call_tool("get_clinvar_meta", {})
    payload = result.structured_content or {}

    assert payload["_meta"]["deprecated"] is True
    assert payload["_meta"]["use_instead"] == "get_server_capabilities"
    # The data is still returned for backward compatibility.
    assert payload["clinvar_release_date"] == "2024-10-15"
