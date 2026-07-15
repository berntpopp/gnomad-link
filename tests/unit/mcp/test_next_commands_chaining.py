"""Discoverability: success payloads emit ready-to-call _meta.next_commands so an
LLM can advance the workflow without re-forming the next call.

Covers the open chain points from the deep audit (disc-2/-3/-4/-6):
search_genes -> get_gene_details, compute_variant_liftover -> get_variant_frequencies,
get_region -> get_gene_variants/get_clinvar_variant_details, and
get_transcript_details -> get_gene_summary.
"""

from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.mcp.facade import create_gnomad_mcp


def _next_commands(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return (payload.get("_meta") or {}).get("next_commands") or []


class _GeneSearchStub:
    async def search_genes(self, query: str, reference_genome: str) -> list[dict[str, Any]]:
        return [{"symbol": "CFTR", "ensembl_id": "ENSG00000001626"}]


@pytest.mark.asyncio
async def test_search_genes_chains_to_get_gene_details() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _GeneSearchStub())
    result = await mcp.call_tool("search_genes", {"query": "CFTR"})
    payload = result.structured_content or {}

    cmds = _next_commands(payload)
    assert cmds and cmds[0]["tool"] == "get_gene_details"
    assert cmds[0]["arguments"] == {"gene": "ENSG00000001626"}


class _LiftoverStub:
    async def liftover_variant(
        self, source_variant_id: str, reference_genome: str
    ) -> list[dict[str, Any]]:
        return [
            {
                "source": {"variant_id": "1-55051215-G-GA", "reference_genome": "GRCh37"},
                "liftover": {"variant_id": "1-54585542-G-GA", "reference_genome": "GRCh38"},
            }
        ]


@pytest.mark.asyncio
async def test_liftover_chains_to_get_variant_frequencies_on_target() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _LiftoverStub())
    result = await mcp.call_tool(
        "compute_variant_liftover",
        {"source_variant_id": "1-55051215-G-GA", "source_genome": "GRCh37"},
    )
    payload = result.structured_content or {}

    cmds = _next_commands(payload)
    assert cmds and cmds[0]["tool"] == "get_variant_frequencies"
    # Forward GRCh37->GRCh38 target frequency lookup uses the GRCh38 default dataset.
    assert cmds[0]["arguments"] == {"variant_id": "1-54585542-G-GA", "dataset": "gnomad_r4"}


class _RegionStub:
    async def get_region(self, chrom: str, start: int, stop: int, dataset: str) -> dict[str, Any]:
        return {
            "region": {
                "chrom": chrom,
                "start": start,
                "stop": stop,
                "genes": [{"gene_id": "ENSG00000141510", "symbol": "TP53"}],
                "clinvar_variants": [{"variant_id": "17-7676154-G-A"}],
            }
        }


@pytest.mark.asyncio
async def test_region_chains_to_gene_variants_and_clinvar() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _RegionStub())
    result = await mcp.call_tool(
        "get_region",
        {"region": "17-7676154-7676254", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    tools = [c["tool"] for c in _next_commands(payload)]
    assert "get_gene_variants" in tools
    assert "get_clinvar_variant_details" in tools


class _TranscriptStub:
    async def get_transcript_details(
        self, *, transcript_id: str, reference_genome: str, include_expression: bool
    ) -> dict[str, Any]:
        return {
            "transcript_id": transcript_id,
            "gene_id": "ENSG00000141510",
            "gene_symbol": "TP53",
            "exons": [],
        }


@pytest.mark.asyncio
async def test_transcript_chains_to_get_gene_summary() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _TranscriptStub())
    result = await mcp.call_tool(
        "get_transcript_details",
        {"transcript_id": "ENST00000269305", "include_expression": False},
    )
    payload = result.structured_content or {}

    cmds = _next_commands(payload)
    assert cmds and cmds[0]["tool"] == "get_gene_summary"
    assert cmds[0]["arguments"] == {"gene": "ENSG00000141510"}
