from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.mcp.facade import create_gnomad_mcp


def _metrics(cf: float, sum_af: float) -> dict[str, Any]:
    return {
        "carrier_frequency": cf,
        "sum_af": sum_af,
        "total_ac": 100,
        "max_an": 10000,
        "genetic_prevalence": sum_af * sum_af,
        "bayesian_prevalence": sum_af * sum_af,
        "method": "hom_exclusion",
    }


class _StubGeneCarrierService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def get_gene_carrier_frequency(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {
            "gene": {"gene_id": "ENSG1", "symbol": "CFTR"},
            "dataset": kwargs.get("dataset", "gnomad_r4"),
            "reference_genome": "GRCh38",
            "settings": {"method": kwargs.get("method", "hom_exclusion")},
            "global": _metrics(0.0568, 0.029157),
            "populations": {
                "afr": _metrics(0.0228, 0.01127),
                "nfe": _metrics(0.0631, 0.031837),
                "asj": _metrics(0.1106, 0.055357),
            },
            "qualifying_variants": [],
            "qualifying_count": 523,
            "sources": {"plof_only": 121, "clinvar_only": 156, "both": 246},
        }


@pytest.mark.asyncio
async def test_gene_carrier_by_symbol_returns_sorted_populations() -> None:
    stub = _StubGeneCarrierService()
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool("compute_gene_carrier_frequency", {"gene_symbol": "CFTR"})
    payload = result.structured_content or {}

    assert payload["gene"]["symbol"] == "CFTR"
    assert payload["global"]["carrier_one_in"] == 18
    assert payload["populations"][0]["population"] == "asj"  # highest carrier first
    assert payload["contributing_variants"]["count"] == 523
    # default settings forwarded to the service via FilterConfig
    cfg = stub.calls[0]["filter_config"]
    assert cfg.lof_hc_enabled is True
    assert cfg.clinvar_star_threshold == 2
    assert stub.calls[0]["method"] == "hom_exclusion"
    next_tools = [c["tool"] for c in payload["_meta"]["next_commands"]]
    assert "compute_gene_carrier_frequency" not in next_tools  # no self-reference


@pytest.mark.asyncio
async def test_gene_carrier_forwards_toggles() -> None:
    stub = _StubGeneCarrierService()
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    await mcp.call_tool(
        "compute_gene_carrier_frequency",
        {
            "gene_symbol": "CFTR",
            "include_missense": False,
            "clinvar_star_threshold": 1,
            "method": "hwe",
            "penetrance": 0.8,
            "exclude_high_af": True,
        },
    )
    kw = stub.calls[0]
    assert kw["filter_config"].missense_enabled is False
    assert kw["filter_config"].clinvar_star_threshold == 1
    assert kw["method"] == "hwe"
    assert kw["penetrance"] == 0.8
    assert kw["exclude_high_af"] is True


@pytest.mark.asyncio
async def test_gene_carrier_requires_exactly_one_gene_arg() -> None:
    stub = _StubGeneCarrierService()
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    none = await mcp.call_tool("compute_gene_carrier_frequency", {})
    assert (none.structured_content or {})["error_code"] == "validation_failed"

    both = await mcp.call_tool(
        "compute_gene_carrier_frequency", {"gene_symbol": "CFTR", "gene_id": "ENSG1"}
    )
    assert (both.structured_content or {})["error_code"] == "validation_failed"
    assert stub.calls == []


@pytest.mark.asyncio
async def test_gene_carrier_registered_and_advertised(fake_service_factory) -> None:
    from gnomad_link.mcp.resources import get_capabilities_resource

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    names = {tool.name for tool in await mcp.list_tools()}
    assert "compute_gene_carrier_frequency" in names
    caps = get_capabilities_resource()
    assert "compute_gene_carrier_frequency" in caps["tools"]
    assert "compute_gene_carrier_frequency" in caps["token_cost_hints"]
    assert "compute_gene_carrier_frequency" in caps["tool_categories"]["gene"]
