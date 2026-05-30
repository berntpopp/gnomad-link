"""Tool-surface tests for search_structural_variants.

Offline: the service factory returns a spy whose search_structural_variants
returns a fixed SV list. Exercises entry-arg dispatch, the DISTINCT sv_dataset
Literal, client-side filters, the empty->success contract, and the
next_commands cross-link to get_structural_variant.
"""

from __future__ import annotations

import pytest

_ROWS = [
    {
        "variant_id": "DEL_19_1",
        "type": "DEL",
        "chrom": "19",
        "pos": 11_089_000,
        "end": 11_133_820,
        "length": 44_820,
        "af": 0.0001,
        "ac": 3,
        "an": 30000,
        "major_consequence": "lof",
    },
    {
        "variant_id": "DUP_19_2",
        "type": "DUP",
        "chrom": "19",
        "pos": 11_100_000,
        "end": 11_200_000,
        "length": 100_000,
        "af": 0.002,
        "ac": 60,
        "an": 30000,
        "major_consequence": "copy_gain",
    },
]


class _SpySvService:
    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        self.rows = _ROWS if rows is None else rows
        self.last_kwargs: dict[str, object] | None = None

    async def search_structural_variants(
        self,
        *,
        gene_symbol: str | None = None,
        gene_id: str | None = None,
        region: str | None = None,
        sv_dataset: str = "gnomad_sv_r4",
    ) -> list[dict[str, object]]:
        self.last_kwargs = {
            "gene_symbol": gene_symbol,
            "gene_id": gene_id,
            "region": region,
            "sv_dataset": sv_dataset,
        }
        return self.rows


@pytest.mark.asyncio
async def test_search_by_gene_symbol_returns_rows() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _SpySvService()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "search_structural_variants",
        {"gene_symbol": "SMARCA4", "sv_dataset": "gnomad_sv_r4"},
    )
    payload = result.structured_content or {}

    assert payload.get("error_code") != "validation_failed", payload
    assert payload["query"] == {"gene_symbol": "SMARCA4", "sv_dataset": "gnomad_sv_r4"}
    assert payload["returned"] == 2
    assert payload["total_seen"] == 2
    assert spy.last_kwargs["gene_symbol"] == "SMARCA4"


@pytest.mark.asyncio
async def test_distinct_sv_dataset_default_is_r4() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _SpySvService()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool("search_structural_variants", {"gene_symbol": "SMARCA4"})
    payload = result.structured_content or {}

    assert payload.get("error_code") != "validation_failed", payload
    assert spy.last_kwargs["sv_dataset"] == "gnomad_sv_r4"


@pytest.mark.asyncio
async def test_invalid_sv_dataset_rejected_by_schema() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _SpySvService()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    # gnomad_r4 is the SNV DatasetId, NOT a StructuralVariantDatasetId.
    result = await mcp.call_tool(
        "search_structural_variants",
        {"gene_symbol": "SMARCA4", "sv_dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    assert payload.get("success") is False
    assert payload.get("error_code") == "validation_failed"
    assert spy.last_kwargs is None


@pytest.mark.asyncio
async def test_requires_exactly_one_entry_arg() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _SpySvService()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    none_result = await mcp.call_tool("search_structural_variants", {})
    none_payload = none_result.structured_content or {}
    assert none_payload.get("error_code") == "validation_failed"

    both_result = await mcp.call_tool(
        "search_structural_variants",
        {"gene_symbol": "SMARCA4", "region": "19-11089000-11200000"},
    )
    both_payload = both_result.structured_content or {}
    assert both_payload.get("error_code") == "validation_failed"


@pytest.mark.asyncio
async def test_sv_type_filter_applied() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _SpySvService()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "search_structural_variants",
        {"gene_symbol": "SMARCA4", "sv_type": "DEL"},
    )
    payload = result.structured_content or {}

    assert [r["variant_id"] for r in payload["structural_variants"]] == ["DEL_19_1"]
    assert payload["truncated"]["kind"] == "structural_variants"
    assert payload["truncated"]["dropped"] == 1


@pytest.mark.asyncio
async def test_empty_result_is_success_not_error() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _SpySvService(rows=[])
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool("search_structural_variants", {"gene_symbol": "NONEXISTENT"})
    payload = result.structured_content or {}

    assert payload.get("success") is not False
    assert payload["returned"] == 0
    assert payload["total_seen"] == 0
    assert payload["structural_variants"] == []


@pytest.mark.asyncio
async def test_next_commands_link_to_get_structural_variant() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _SpySvService()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool("search_structural_variants", {"gene_symbol": "SMARCA4"})
    payload = result.structured_content or {}
    next_commands = payload["_meta"]["next_commands"]

    assert len(next_commands) <= 3
    assert all(cmd["tool"] == "get_structural_variant" for cmd in next_commands)
    ids = [cmd["arguments"]["variant_id"] for cmd in next_commands]
    assert ids == ["DEL_19_1", "DUP_19_2"]
    assert all(cmd["arguments"]["dataset"] == "gnomad_sv_r4" for cmd in next_commands)


@pytest.mark.asyncio
async def test_region_dispatch_forwards_region() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _SpySvService()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "search_structural_variants",
        {"region": "19-11089000-11200000", "sv_dataset": "gnomad_sv_r2_1"},
    )
    payload = result.structured_content or {}

    assert payload.get("error_code") != "validation_failed", payload
    assert spy.last_kwargs["region"] == "19-11089000-11200000"
    assert spy.last_kwargs["sv_dataset"] == "gnomad_sv_r2_1"
    assert payload["query"]["region"] == "19-11089000-11200000"


@pytest.mark.asyncio
async def test_tool_is_registered_with_variant_tag_and_open_world() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=lambda: _SpySvService())
    tools_by_name = {tool.name: tool for tool in await mcp.list_tools()}

    assert "search_structural_variants" in tools_by_name
    tool = tools_by_name["search_structural_variants"]
    assert tool.tags == {"variant", "search"}
    assert tool.annotations is not None
    assert tool.annotations.openWorldHint is True
