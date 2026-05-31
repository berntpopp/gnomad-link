"""Task 9: universal _meta.next_commands on detail/SV/gene-variants/mito/transcript.

Every success payload from these tools must carry a non-empty, structured,
directly-callable _meta.next_commands list. Each entry is {tool, arguments} with
a non-empty tool name and (where reasonable) non-empty arguments. These tests
pin the previously-missing or conditional emission paths:

- get_variant_details: both compact and full paths emit for_variant(...) (2 entries).
- get_gene_variants: get_gene_details follow-up + a clinvar entry when a variant exists.
- get_structural_variant: a region-based chain built from chrom/pos/end.
- get_mitochondrial_variant WITHOUT gene_symbol: the unconditional fallback path.
- get_transcript_details WITHOUT gene_id: the unconditional fallback path.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

import mcp.types
from gnomad_link.mcp.facade import create_gnomad_mcp


async def _invoke(mcp_instance: Any, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Route through the SDK lowlevel handler so output-schema validation runs."""
    handler = mcp_instance._mcp_server.request_handlers[mcp.types.CallToolRequest]
    request = mcp.types.CallToolRequest(
        method="tools/call",
        params=mcp.types.CallToolRequestParams(name=tool, arguments=arguments),
    )
    result = await handler(request)
    call_result = result.root if hasattr(result, "root") else result
    assert isinstance(call_result, mcp.types.CallToolResult)
    if call_result.structuredContent is not None:
        return dict(call_result.structuredContent)
    if call_result.content:
        text = getattr(call_result.content[0], "text", None)
        if isinstance(text, str):
            return json.loads(text)
    return {}


def _next_commands(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return (payload.get("_meta") or {}).get("next_commands") or []


def _assert_well_formed(cmds: list[dict[str, Any]], *, require_args: bool = True) -> None:
    assert isinstance(cmds, list) and cmds, cmds
    for entry in cmds:
        assert isinstance(entry, dict), entry
        assert isinstance(entry.get("tool"), str) and entry["tool"], entry
        assert isinstance(entry.get("arguments"), dict), entry
        if require_args:
            assert entry["arguments"], entry


# --- A) get_variant_details ------------------------------------------------

_RAW_VARIANT = {
    "variant_id": "7-117559590-ATCT-A",
    "reference_genome": "GRCh38",
    "pos": 117559590,
    "ref": "ATCT",
    "alt": "A",
    "major_consequence": "inframe_deletion",
    "transcript_consequences": [
        {
            "transcript_id": "ENST00000003084",
            "gene_symbol": "CFTR",
            "canonical": True,
            "major_consequence": "inframe_deletion",
        }
    ],
    "in_silico_predictors": [{"id": "cadd", "value": "19.2", "flags": []}],
    "clinvar": {"clinical_significance": "Pathogenic"},
    "exome": {"ac": 1000, "an": 1200000, "populations": []},
    "genome": None,
}


class _VariantDetailsStub:
    async def get_variant(self, variant_id: str, dataset: str) -> dict[str, Any]:
        return {"variant": dict(_RAW_VARIANT)}


@pytest.mark.asyncio
async def test_variant_details_compact_emits_for_variant() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _VariantDetailsStub())
    payload = await _invoke(
        mcp,
        "get_variant_details",
        {"variant_id": "7-117559590-ATCT-A", "dataset": "gnomad_r4"},
    )
    assert payload.get("error_code") is None, payload
    cmds = _next_commands(payload)
    _assert_well_formed(cmds)
    tools = [c["tool"] for c in cmds]
    assert tools == ["get_variant_frequencies", "get_clinvar_variant_details"], cmds
    assert cmds[0]["arguments"]["variant_id"] == "7-117559590-ATCT-A"
    assert cmds[0]["arguments"]["dataset"] == "gnomad_r4"


@pytest.mark.asyncio
async def test_variant_details_full_emits_for_variant() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _VariantDetailsStub())
    payload = await _invoke(
        mcp,
        "get_variant_details",
        {
            "variant_id": "7-117559590-ATCT-A",
            "dataset": "gnomad_r4",
            "response_mode": "full",
        },
    )
    assert payload.get("error_code") is None, payload
    cmds = _next_commands(payload)
    _assert_well_formed(cmds)
    assert [c["tool"] for c in cmds] == [
        "get_variant_frequencies",
        "get_clinvar_variant_details",
    ], cmds


# --- B) get_gene_variants --------------------------------------------------


class _GeneVariantsStub:
    async def get_gene_variants(self, gene_id: str, dataset: str) -> list[dict[str, Any]]:
        return [
            {
                "variant_id": "12-1-A-T",
                "pos": 1,
                "ref": "A",
                "alt": "T",
                "consequence": "stop_gained",
                "af": 0.0005,
                "ac": 5,
                "exome": {"ac": 5, "an": 10_000, "af": 0.0005, "populations": []},
                "genome": None,
            }
        ]


class _EmptyGeneVariantsStub:
    async def get_gene_variants(self, gene_id: str, dataset: str) -> list[dict[str, Any]]:
        return []


@pytest.mark.asyncio
async def test_gene_variants_chains_to_gene_details_and_clinvar() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _GeneVariantsStub())
    payload = await _invoke(mcp, "get_gene_variants", {"gene_id": "ENSG00000169174"})
    assert payload.get("error_code") is None, payload
    cmds = _next_commands(payload)
    _assert_well_formed(cmds)
    assert cmds[0]["tool"] == "get_gene_details"
    assert cmds[0]["arguments"] == {"gene_id": "ENSG00000169174"}
    clinvar = [c for c in cmds if c["tool"] == "get_clinvar_variant_details"]
    assert clinvar, cmds
    assert clinvar[0]["arguments"] == {"variant_id": "12-1-A-T"}


@pytest.mark.asyncio
async def test_gene_variants_no_variants_still_emits_gene_details() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _EmptyGeneVariantsStub())
    payload = await _invoke(mcp, "get_gene_variants", {"gene_id": "ENSG00000169174"})
    assert payload.get("error_code") is None, payload
    cmds = _next_commands(payload)
    _assert_well_formed(cmds)
    assert [c["tool"] for c in cmds] == ["get_gene_details"], cmds
    # No variant -> no clinvar follow-up.
    assert all(c["tool"] != "get_clinvar_variant_details" for c in cmds)


# --- C) get_structural_variant ---------------------------------------------


def _sv_payload() -> dict[str, Any]:
    return {
        "variant_id": "DEL_chr1_1234abcd",
        "reference_genome": "GRCh38",
        "chrom": "1",
        "type": "DEL",
        "pos": 1000,
        "end": 2000,
        "af": 0.01,
        "ac": 10,
        "an": 1000,
        "consequences": [{"consequence": "lof", "genes": ["GENEA"]}],
        "populations": [{"id": "afr", "ac": 1, "an": 100}],
    }


class _SVStub:
    async def get_structural_variant(self, variant_id: str, dataset: str) -> dict[str, Any]:
        return {"structural_variant": _sv_payload()}


@pytest.mark.asyncio
async def test_structural_variant_emits_region_chain() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _SVStub())
    payload = await _invoke(mcp, "get_structural_variant", {"variant_id": "DEL_chr1_1234abcd"})
    assert payload.get("error_code") is None, payload
    cmds = _next_commands(payload)
    _assert_well_formed(cmds)
    tools = [c["tool"] for c in cmds]
    assert "search_structural_variants" in tools
    assert "get_region" in tools
    region = "1-1000-2000"
    for c in cmds:
        assert c["arguments"].get("region") == region, c


# --- D) get_mitochondrial_variant without gene_symbol ----------------------


class _MitoNoGeneStub:
    async def get_mitochondrial_variant(self, variant_id: str, dataset: str) -> dict[str, Any]:
        return {
            "mitochondrial_variant": {
                "variant_id": "M-3243-A-G",
                "pos": 3243,
                "ref": "A",
                "alt": "G",
                "ac_het": 5,
                "ac_hom": 0,
                "an": 100,
                "populations": [],
            }
        }


@pytest.mark.asyncio
async def test_mitochondrial_variant_without_gene_still_emits() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _MitoNoGeneStub())
    payload = await _invoke(
        mcp,
        "get_mitochondrial_variant",
        {"variant_id": "M-3243-A-G", "dataset": "gnomad_r4"},
    )
    assert payload.get("error_code") != "validation_failed", payload
    cmds = _next_commands(payload)
    _assert_well_formed(cmds)
    # Position-based fallback prefers a get_region anchor.
    assert cmds[0]["tool"] == "get_region", cmds
    assert cmds[0]["arguments"]["region"] == "M-3243-3244", cmds


# --- E) get_transcript_details without gene_id -----------------------------


class _TranscriptNoGeneStub:
    async def get_transcript_details(
        self, *, transcript_id: str, reference_genome: str, include_expression: bool
    ) -> dict[str, Any]:
        return {"transcript_id": transcript_id, "exons": []}


@pytest.mark.asyncio
async def test_transcript_details_without_gene_still_emits() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: _TranscriptNoGeneStub())
    payload = await _invoke(
        mcp,
        "get_transcript_details",
        {"transcript_id": "ENST00000269305", "include_expression": False},
    )
    assert payload.get("error_code") is None, payload
    cmds = _next_commands(payload)
    # No-context fallback: get_server_capabilities legitimately takes no args.
    _assert_well_formed(cmds, require_args=False)
    assert cmds[0]["tool"] == "get_server_capabilities", cmds
