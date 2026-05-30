from __future__ import annotations

import re

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
    "liftover_variant",
    "get_structural_variant",
    "get_mitochondrial_variant",
    "get_region",
    "get_transcript_details",
    "search_genes",
    "resolve_variant_id",
    "search_variants",  # deprecated alias retained for one release
    "compute_carrier_frequency",
    "get_gnomad_diagnostics",
    "compare_variant_across_datasets",
}

EXPECTED_DATA_TOOLS = EXPECTED_TOOLS - {"get_server_capabilities", "get_gnomad_diagnostics"}

EXPECTED_RESOURCE_URIS = {
    "gnomad://capabilities",
    "gnomad://usage",
    "gnomad://research-use",
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
async def test_capabilities_tool_is_closed_world(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    tools_by_name = {tool.name: tool for tool in await mcp.list_tools()}
    ann = tools_by_name["get_server_capabilities"].annotations

    assert ann is not None
    assert ann.openWorldHint is False


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
async def test_get_gnomad_diagnostics_returns_health_and_recent_errors(
    fake_service_factory,
) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    tools_by_name = {tool.name: tool for tool in await mcp.list_tools()}
    assert "get_gnomad_diagnostics" in tools_by_name
    tool = tools_by_name["get_gnomad_diagnostics"]
    # Must be closed-world (local health data, no upstream call)
    assert tool.annotations is not None
    assert tool.annotations.openWorldHint is False


@pytest.mark.asyncio
async def test_diagnostics_tool_is_closed_world(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    tools_by_name = {tool.name: tool for tool in await mcp.list_tools()}
    ann = tools_by_name["get_gnomad_diagnostics"].annotations
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
    assert tools_by_name["liftover_variant"].tags == {"coordinates"}
    assert tools_by_name["get_gnomad_diagnostics"].tags == {"metadata", "diagnostics"}


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


@pytest.mark.asyncio
async def test_get_clinvar_meta_marks_deprecated() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    class _StubMetaService:
        async def get_clinvar_meta(self) -> dict[str, object]:
            return {"clinvar_release_date": "2024-10-15"}

    mcp = create_gnomad_mcp(service_factory=lambda: _StubMetaService())
    result = await mcp.call_tool("get_clinvar_meta", {})
    payload = result.structured_content or {}

    assert payload["_meta"]["deprecated"] is True
    assert payload["_meta"]["use_instead"] == "get_server_capabilities"
    # The data is still returned for backward compatibility.
    assert payload["clinvar_release_date"] == "2024-10-15"
