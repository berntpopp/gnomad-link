from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.mcp.facade import create_gnomad_mcp


class _StubGeneSummaryService:
    """Stub FrequencyService exposing only get_gene_summary."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def get_gene_summary(
        self,
        *,
        gene_id: str | None = None,
        gene_symbol: str | None = None,
        dataset: str = "gnomad_r4",
        include_expression: bool = True,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "gene_id": gene_id,
                "gene_symbol": gene_symbol,
                "dataset": dataset,
                "include_expression": include_expression,
            }
        )
        return {
            "gene_id": "ENSG00000169174",
            "symbol": "PCSK9",
            "name": "proprotein convertase subtilisin/kexin type 9",
            "coords": {"chrom": "1", "start": 55039447, "stop": 55064852},
            "dataset": dataset,
            "reference_genome": "GRCh38",
            "constraint": {"pli": 0.01, "oe_lof": 0.8},
            "canonical_transcript_id": "ENST00000302118",
            "mane_select_transcript": {"ensembl_id": "ENST00000302118", "refseq_id": "NM_174936"},
            "clinvar_variants": [
                {
                    "variant_id": "1-1-A-G",
                    "clinical_significance": "Pathogenic",
                    "gold_stars": 3,
                    "major_consequence": "missense_variant",
                },
                {
                    "variant_id": "1-2-A-G",
                    "clinical_significance": "Likely pathogenic",
                    "gold_stars": 1,
                    "major_consequence": "missense_variant",
                },
                {
                    "variant_id": "1-3-A-G",
                    "clinical_significance": "Benign",
                    "gold_stars": 2,
                    "major_consequence": "synonymous_variant",
                },
            ],
            "pext": {"flags": [], "regions": []},
            "expression": {
                "source_build": "GRCh37",
                "mean_pext": 0.7,
                "top_tissues": [{"tissue": "Liver", "value": 42.0}],
            },
            "flags": [],
            "partial": False,
        }


@pytest.mark.asyncio
async def test_get_gene_summary_compact_shapes_clinvar_and_meta() -> None:
    stub = _StubGeneSummaryService()
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool("get_gene_summary", {"gene_symbol": "PCSK9"})
    payload = result.structured_content or {}

    assert payload["symbol"] == "PCSK9"
    assert payload["clinvar_summary"]["pathogenic_count"] == 2
    assert payload["clinvar_summary"]["top_pathogenic"][0]["variant_id"] == "1-1-A-G"
    # Compact mode replaces the raw clinvar_variants list with the ranked summary.
    assert "clinvar_variants" not in payload
    assert payload["expression"]["source_build"] == "GRCh37"
    # next_commands cross-link, capped at 3, no self-reference.
    next_cmds = payload["_meta"]["next_commands"]
    tools = [c["tool"] for c in next_cmds]
    assert tools == ["get_gene_variants", "get_clinvar_variant_details", "get_coverage"]
    assert "get_gene_summary" not in tools
    # Research-use meta injected by run_mcp_tool.
    assert payload["_meta"]["unsafe_for_clinical_use"] is True
    assert "gnomad_release" in payload["_meta"]
    assert stub.calls[0]["gene_symbol"] == "PCSK9"


@pytest.mark.asyncio
async def test_get_gene_summary_full_returns_raw_clinvar_variants() -> None:
    stub = _StubGeneSummaryService()
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "get_gene_summary", {"gene_symbol": "PCSK9", "response_mode": "full"}
    )
    payload = result.structured_content or {}

    assert isinstance(payload["clinvar_variants"], list)
    assert len(payload["clinvar_variants"]) == 3
    assert "clinvar_summary" not in payload


@pytest.mark.asyncio
async def test_include_clinvar_false_drops_clinvar_block() -> None:
    stub = _StubGeneSummaryService()
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "get_gene_summary", {"gene_symbol": "PCSK9", "include_clinvar": False}
    )
    payload = result.structured_content or {}

    assert "clinvar_summary" not in payload
    assert "clinvar_variants" not in payload
    # Other sections remain.
    assert payload["constraint"] == {"pli": 0.01, "oe_lof": 0.8}


@pytest.mark.asyncio
async def test_expression_only_projection() -> None:
    stub = _StubGeneSummaryService()
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "get_gene_summary",
        {"gene_symbol": "PCSK9", "include_clinvar": False, "include_constraint": False},
    )
    payload = result.structured_content or {}

    assert "clinvar_summary" not in payload
    assert "clinvar_variants" not in payload
    assert "constraint" not in payload
    assert payload["expression"]["mean_pext"] == 0.7  # expression still present


@pytest.mark.asyncio
async def test_include_expression_false_skips_service_fetch() -> None:
    stub = _StubGeneSummaryService()
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "get_gene_summary", {"gene_symbol": "PCSK9", "include_expression": False}
    )
    payload = result.structured_content or {}

    assert "expression" not in payload
    # The flag is forwarded to the service so the GTEx call is skipped upstream.
    assert stub.calls[0]["include_expression"] is False


@pytest.mark.asyncio
async def test_get_gene_summary_requires_exactly_one_identifier() -> None:
    stub = _StubGeneSummaryService()
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    none_given = (await mcp.call_tool("get_gene_summary", {})).structured_content or {}
    assert none_given["error_code"] == "validation_failed"

    both_given = (
        await mcp.call_tool(
            "get_gene_summary",
            {"gene_symbol": "PCSK9", "gene_id": "ENSG00000169174"},
        )
    ).structured_content or {}
    assert both_given["error_code"] == "validation_failed"
    # Service is never invoked when identifier validation fails.
    assert stub.calls == []


@pytest.mark.asyncio
async def test_get_gene_summary_advertised_in_capabilities() -> None:
    from gnomad_link.mcp.resources import get_capabilities_resource

    caps = get_capabilities_resource()
    assert "get_gene_summary" in caps["tools"]
    assert "get_gene_summary" in caps["token_cost_hints"]
    assert len(caps["token_cost_hints"]["get_gene_summary"]) <= 80
    assert "get_gene_summary" in caps["tool_categories"]["gene"]
