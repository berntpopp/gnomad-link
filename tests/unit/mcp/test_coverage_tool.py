from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.mcp.facade import create_gnomad_mcp


class _StubCoverageService:
    """Captures the get_coverage kwargs the tool passes."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def get_coverage(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        scope = kwargs["scope"]
        if scope == "gene":
            return {
                "gene": {
                    "gene_id": "ENSG00000169174",
                    "symbol": "PCSK9",
                    "coverage": {
                        "exome": [
                            {
                                "pos": 100,
                                "mean": 31.0,
                                "median": 31,
                                "over_20": 0.99,
                                "over_30": 0.8,
                            }
                        ],
                        "genome": [],
                    },
                }
            }
        if scope == "region":
            return {
                "region": {
                    "chrom": kwargs["chrom"],
                    "start": kwargs["start"],
                    "stop": kwargs["stop"],
                    "coverage": {
                        "exome": [
                            {
                                "pos": kwargs["start"],
                                "mean": 30.0,
                                "median": 30,
                                "over_20": 0.98,
                                "over_30": 0.7,
                            }
                        ],
                        "genome": [],
                    },
                }
            }
        return {
            "variant": {
                "variant_id": kwargs["variant_id"],
                "coverage": {
                    "exome": {"mean": 31.0, "median": 31, "over_20": 0.99, "over_30": 0.82},
                    "genome": {"mean": 27.0, "median": 27, "over_20": 0.95, "over_30": 0.55},
                },
            }
        }


@pytest.mark.asyncio
async def test_get_coverage_gene_scope_by_symbol() -> None:
    service = _StubCoverageService()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    result = await mcp.call_tool("get_coverage", {"gene_symbol": "PCSK9"})
    payload = result.structured_content or {}

    assert payload["scope"] == "gene"
    assert payload["identity"]["symbol"] == "PCSK9"
    assert service.calls[0]["scope"] == "gene"
    assert service.calls[0]["gene_symbol"] == "PCSK9"
    assert payload["exome"]["summary"]["mean_coverage"] == 31.0


@pytest.mark.asyncio
async def test_get_coverage_variant_scope_is_scalar_and_links_to_frequencies() -> None:
    service = _StubCoverageService()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    result = await mcp.call_tool(
        "get_coverage", {"variant_id": "1-55039447-A-G", "dataset": "gnomad_r4"}
    )
    payload = result.structured_content or {}

    assert payload["scope"] == "variant"
    assert "bins" not in payload["exome"]
    next_tools = [c["tool"] for c in payload["_meta"]["next_commands"]]
    assert "get_variant_frequencies" in next_tools
    assert "get_coverage" not in next_tools  # no self-reference


@pytest.mark.asyncio
async def test_get_coverage_region_scope_caps_span_at_100kb() -> None:
    service = _StubCoverageService()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    # 500kb span exceeds the 100kb cap.
    result = await mcp.call_tool("get_coverage", {"region": "1-55000000-55500000"})
    payload = result.structured_content or {}

    assert payload["scope"] == "region"
    # Span was clamped before the service call.
    assert service.calls[0]["stop"] - service.calls[0]["start"] == 100_000


@pytest.mark.asyncio
async def test_get_coverage_requires_exactly_one_scope_arg() -> None:
    service = _StubCoverageService()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    result = await mcp.call_tool("get_coverage", {})
    payload = result.structured_content or {}

    assert payload["success"] is False
    assert payload["error_code"] == "validation_failed"
    assert service.calls == []


@pytest.mark.asyncio
async def test_get_coverage_rejects_two_scope_args() -> None:
    service = _StubCoverageService()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    result = await mcp.call_tool(
        "get_coverage", {"gene_symbol": "PCSK9", "variant_id": "1-55039447-A-G"}
    )
    payload = result.structured_content or {}

    assert payload["error_code"] == "validation_failed"
    assert service.calls == []


@pytest.mark.asyncio
async def test_get_coverage_region_build_mismatch_against_r4() -> None:
    service = _StubCoverageService()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    # chr1 is longer on GRCh37 (249,250,621 bp) than GRCh38 (248,956,422 bp),
    # so pos ~248.99Mb is valid only on GRCh37 and infers a GRCh37 build.
    # Querying it against gnomad_r4 (GRCh38) must raise build_mismatch.
    result = await mcp.call_tool(
        "get_coverage", {"region": "1-248990000-248990100", "dataset": "gnomad_r4"}
    )
    payload = result.structured_content or {}

    assert payload["error_code"] == "build_mismatch"
    assert payload["fallback_tool"] == "liftover_variant"
    assert service.calls == []


@pytest.mark.asyncio
async def test_get_coverage_registered_and_advertised(fake_service_factory) -> None:
    from gnomad_link.mcp.resources import get_capabilities_resource

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    names = {tool.name for tool in await mcp.list_tools()}
    assert "get_coverage" in names
    caps = get_capabilities_resource()
    assert "get_coverage" in caps["tools"]
    assert "get_coverage" in caps["token_cost_hints"]
    assert "get_coverage" in caps["tool_categories"]["coordinates"]
