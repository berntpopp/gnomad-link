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
    "get_gnomad_diagnostics",
}

EXPECTED_DATA_TOOLS = EXPECTED_TOOLS - {"get_server_capabilities", "get_gnomad_diagnostics"}

EXPECTED_RESOURCE_URIS = {
    "gnomad://capabilities",
    "gnomad://usage",
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
