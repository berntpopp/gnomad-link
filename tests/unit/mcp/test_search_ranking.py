"""search_genes match_quality ranking tests.

Task A6 of the MCP Facade Polish plan: when search_genes returns multiple
hits, the tool must annotate each with a match_quality marker and sort the
list so that exact symbol matches win over exact Ensembl id, then prefix,
then substring. Stable index order is preserved within a tier.
"""

from __future__ import annotations

import pytest

from gnomad_link.models import GeneSearchResult


class _StubGeneService:
    """FrequencyService stub whose search_genes returns a controlled list."""

    def __init__(self, results: list[GeneSearchResult]) -> None:
        self._results = results
        self.last_query: str | None = None
        self.last_reference_genome: str | None = None

    async def search_genes(self, query: str, reference_genome: str) -> list[GeneSearchResult]:
        self.last_query = query
        self.last_reference_genome = reference_genome
        return list(self._results)


@pytest.mark.asyncio
async def test_exact_symbol_ranks_first() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubGeneService(
        [
            GeneSearchResult(symbol="BRCA1P1", ensembl_id="ENSG00000000001"),
            GeneSearchResult(symbol="BRCA1", ensembl_id="ENSG00000012048"),
            GeneSearchResult(symbol="BRCA10", ensembl_id="ENSG00000000002"),
        ]
    )
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool("search_genes", {"query": "BRCA1"})
    payload = result.structured_content or {}
    results = payload["results"]

    assert results[0]["symbol"] == "BRCA1"
    assert results[0]["match_quality"] == "exact_symbol"
    assert results[1]["symbol"] == "BRCA1P1"
    assert results[1]["match_quality"] == "prefix"
    assert results[2]["symbol"] == "BRCA10"
    assert results[2]["match_quality"] == "prefix"


@pytest.mark.asyncio
async def test_exact_ensembl_id_wins_over_prefix() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubGeneService(
        [
            GeneSearchResult(symbol="OTHER", ensembl_id="ENSG00000012048AB"),
            GeneSearchResult(symbol="DIFFERENT", ensembl_id="ENSG00000012048"),
        ]
    )
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool("search_genes", {"query": "ENSG00000012048"})
    payload = result.structured_content or {}
    results = payload["results"]

    assert results[0]["ensembl_id"] == "ENSG00000012048"
    assert results[0]["match_quality"] == "exact_ensembl_id"
    assert results[1]["match_quality"] == "prefix"


@pytest.mark.asyncio
async def test_substring_match() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubGeneService([GeneSearchResult(symbol="ABRCA1", ensembl_id="X")])
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool("search_genes", {"query": "BRC"})
    payload = result.structured_content or {}
    results = payload["results"]

    assert results[0]["match_quality"] == "substring"


@pytest.mark.asyncio
async def test_match_quality_case_insensitive() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubGeneService([GeneSearchResult(symbol="BRCA1", ensembl_id="ENSG00000012048")])
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool("search_genes", {"query": "brca1"})
    payload = result.structured_content or {}
    results = payload["results"]

    assert results[0]["match_quality"] == "exact_symbol"


@pytest.mark.asyncio
async def test_short_family_prefix_with_no_exact_match_emits_search_hint() -> None:
    """F4: gnomAD autocomplete omits some family members for a short prefix; the
    tool surfaces an actionable recovery hint instead of a silently-incomplete list."""
    from gnomad_link.mcp.facade import create_gnomad_mcp

    # Mirrors gnomAD's real 'GRIN' result set (no GRIN1/GRIN2B, no exact match).
    stub = _StubGeneService(
        [
            GeneSearchResult(symbol="GRINA", ensembl_id="ENSG00000000001"),
            GeneSearchResult(symbol="GRIN2A", ensembl_id="ENSG00000000002"),
            GeneSearchResult(symbol="GCOM1", ensembl_id="ENSG00000000003"),
        ]
    )
    mcp = create_gnomad_mcp(service_factory=lambda: stub)
    result = await mcp.call_tool("search_genes", {"query": "GRIN"})
    payload = result.structured_content or {}

    assert "search_hint" in payload
    assert "full symbol" in payload["search_hint"]


@pytest.mark.asyncio
async def test_exact_match_suppresses_search_hint() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubGeneService([GeneSearchResult(symbol="BRCA1", ensembl_id="ENSG00000012048")])
    mcp = create_gnomad_mcp(service_factory=lambda: stub)
    result = await mcp.call_tool("search_genes", {"query": "BRCA1"})
    payload = result.structured_content or {}

    assert "search_hint" not in payload
