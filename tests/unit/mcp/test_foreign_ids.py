"""An identifier in a namespace a tool does not take names its converter (router #343)."""

from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.api import DataNotFoundError
from gnomad_link.mcp.facade import create_gnomad_mcp

HGVS = "NM_004333.6:c.1799T>A"


class _Stub:
    """Records every service call: a rejected input must never reach upstream."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    async def search_genes(self, query: str, reference_genome: str | None = None) -> list[Any]:
        self.calls.append(("search_genes", query))
        return []

    async def search_variants(self, query: str, dataset: str = "gnomad_r4") -> list[str]:
        self.calls.append(("search_variants", query))
        return []

    async def get_gene_variants(self, gene_id: str, dataset: str = "gnomad_r4") -> list[Any]:
        self.calls.append(("get_gene_variants", gene_id))
        return []

    async def get_gene_with_variants(self, gene_symbol: str, dataset: str) -> dict[str, Any]:
        self.calls.append(("get_gene_with_variants", gene_symbol))
        if gene_symbol != "KRAS":
            raise DataNotFoundError("Gene not found")
        return {"gene_id": "ENSG00000133703", "variants": [{"variant_id": "12-25245350-C-T"}]}


async def _call(tool: str, **arguments: Any) -> tuple[dict[str, Any], _Stub]:
    stub = _Stub()
    result = await create_gnomad_mcp(service_factory=lambda: stub).call_tool(tool, arguments)
    return result.structured_content or {}, stub


def _assert_converter(payload: dict[str, Any], field: str, command: dict[str, Any]) -> None:
    assert payload["success"] is False, payload
    assert payload["error_code"] == "invalid_input"
    assert payload["field"] == field
    assert payload["allowed_values"]
    assert payload["retryable"] is False
    assert payload["_meta"]["next_commands"][0] == command
    assert (payload["fallback_tool"], payload["fallback_args"]) == (
        command["tool"],
        command["arguments"],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("value", "command"),
    [
        ("HGNC:6407", {"tool": "hgnc_resolve_symbol", "arguments": {"query": "HGNC:6407"}}),
        ("NM_004985.5", {"tool": "hgnc_resolve_symbol", "arguments": {"query": "NM_004985.5"}}),
        (
            "NCBIGene:3845",
            {
                "tool": "hgnc_resolve_gene_by_xref",
                "arguments": {"source": "entrez_id", "value": "3845"},
            },
        ),
        (
            "ENST00000311936",
            {"tool": "get_transcript_details", "arguments": {"transcript_id": "ENST00000311936"}},
        ),
    ],
)
@pytest.mark.parametrize(
    ("tool", "field"),
    [
        ("search_genes", "query"),
        ("get_gene_details", "gene"),
        ("get_gene_variants", "gene_id"),
        ("get_gene_summary", "gene"),
        ("compute_gene_carrier_frequency", "gene"),
        ("get_coverage", "target"),
        ("search_structural_variants", "target"),
    ],
)
async def test_foreign_gene_id_names_the_converter(
    tool: str, field: str, value: str, command: dict[str, Any]
) -> None:
    payload, stub = await _call(tool, **{field: value})
    _assert_converter(payload, field, command)
    assert stub.calls == []


@pytest.mark.asyncio
async def test_gene_variants_accepts_a_symbol_and_echoes_resolved_from() -> None:
    payload, stub = await _call("get_gene_variants", gene_id="KRAS")
    assert payload["success"] is True, payload
    assert stub.calls == [("get_gene_with_variants", "KRAS")]  # one request, no pre-lookup
    assert payload["resolved_from"] == {
        "input": "KRAS",
        "form": "symbol",
        "resolved_to": "ENSG00000133703",
    }
    assert payload["_meta"]["next_commands"][0]["arguments"] == {"gene": "ENSG00000133703"}


@pytest.mark.asyncio
async def test_gene_variants_by_ensembl_id_has_no_resolved_from() -> None:
    payload, stub = await _call("get_gene_variants", gene_id="ENSG00000133703")
    assert payload["success"] is True, payload
    assert stub.calls == [("get_gene_variants", "ENSG00000133703")]
    assert "resolved_from" not in payload


@pytest.mark.asyncio
async def test_gene_variants_unknown_symbol_is_not_found_pointing_at_gene_search() -> None:
    payload, _ = await _call("get_gene_variants", gene_id="NOTAGENE")
    assert payload["error_code"] == "not_found"
    assert payload["_meta"]["next_commands"][0] == {
        "tool": "search_genes",
        "arguments": {"query": "NOTAGENE"},
    }


@pytest.mark.asyncio
async def test_gene_variants_rejects_a_malformed_gene_id() -> None:
    payload, stub = await _call("get_gene_variants", gene_id="BRCA1 gene")
    assert payload["error_code"] == "invalid_input"
    assert stub.calls == []


@pytest.mark.asyncio
async def test_search_genes_empty_for_a_symbol_shaped_query_points_at_hgnc() -> None:
    # Honest empty stays a success; the UniProt shape is not rejected (P2RY12 is a symbol).
    payload, stub = await _call("search_genes", query="P01116")
    assert payload["success"] is True
    assert payload["total_count"] == 0
    assert stub.calls == [("search_genes", "P01116")]
    assert payload["_meta"]["next_commands"] == [
        {"tool": "hgnc_resolve_symbol", "arguments": {"query": "P01116"}}
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", ["resolve_variant_id", "search_variants"])
async def test_resolver_detects_hgvs_before_upstream(tool: str) -> None:
    payload, stub = await _call(tool, query=HGVS, dataset="gnomad_r2_1")
    _assert_converter(
        payload,
        "query",
        {
            "tool": "vep_recode_variant",
            "arguments": {"variants": [HGVS], "fields": "vcf_string", "assembly": "GRCh37"},
        },
    )
    assert stub.calls == []


@pytest.mark.asyncio
async def test_hgvs_without_a_reference_gets_no_converter_call() -> None:
    payload, stub = await _call("resolve_variant_id", query="c.1799T>A")
    assert payload["error_code"] == "invalid_input"
    assert payload["field"] == "query"
    assert [c["tool"] for c in payload["_meta"]["next_commands"]] == ["get_diagnostics"]
    assert stub.calls == []


@pytest.mark.asyncio
async def test_resolver_still_sends_rsids_and_coordinates_upstream() -> None:
    for query in ("rs121913529", "12-25245350-C-T", "12:25245350"):
        payload, stub = await _call("resolve_variant_id", query=query)
        assert payload["success"] is True, payload
        assert stub.calls == [("search_variants", query)]


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", ["get_variant_frequencies", "get_variant_details"])
async def test_hgvs_failing_the_variant_id_schema_names_the_converter(tool: str) -> None:
    payload, stub = await _call(tool, variant_id=HGVS)
    _assert_converter(
        payload,
        "variant_id",
        {
            "tool": "vep_recode_variant",
            "arguments": {"variants": [HGVS], "fields": "vcf_string"},
        },
    )
    assert stub.calls == []


@pytest.mark.asyncio
async def test_mitochondrial_hgvs_names_the_mito_tool() -> None:
    payload, stub = await _call("resolve_variant_id", query="m.3243A>G")
    _assert_converter(
        payload,
        "query",
        {"tool": "get_mitochondrial_variant", "arguments": {"variant_id": "M-3243-A-G"}},
    )
    assert "M-POS-REF-ALT" in payload["recovery"]
    assert stub.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["KRAS:p.G12D", "rs1:c.35G>A"])
async def test_hgvs_on_a_reference_no_recoder_can_place_gets_no_converter(query: str) -> None:
    payload, _ = await _call("resolve_variant_id", query=query)
    assert payload["error_code"] == "invalid_input"
    assert [c["tool"] for c in payload["_meta"]["next_commands"]] == ["get_diagnostics"]


def test_hostile_text_is_never_echoed_into_a_converter_call() -> None:
    from gnomad_link.mcp.foreign_ids import foreign_recovery, redirect_validation_payload

    bidi = "x:c.\u202eevil\u200b_ignore_previous"
    assert foreign_recovery(bidi, "variant") is None
    assert foreign_recovery("NM_004333.6:c.1799" + "A" * 5000, "variant") is None
    assert foreign_recovery("HGNC:\u0661\u0662\u0663", "gene") is None  # non-Latin digits
    assert foreign_recovery("\u0661\u0662\u0663", "gene") is None
    payload: dict[str, Any] = {"_meta": {"next_commands": []}}
    redirect_validation_payload(
        payload, [{"loc": ("variant_id",), "input": "x:c." + "A" * 5000 + "\u202e\x00"}]
    )
    assert payload == {"_meta": {"next_commands": []}}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "PTEN c.-72C>T",
        "PTEN:c.-72C>T",
        "PTEN c.226_228del p.(Leu76del)",
        "BRCA2 c.3901ACT[1]",
        "BRAF p.V600E",
    ],
)
async def test_gene_symbol_hgvs_is_answered_locally_without_a_search_genes_fallback(
    query: str,
) -> None:
    """#149: 'GENE c.change' never reaches upstream and never offers search_genes."""
    payload, stub = await _call("resolve_variant_id", query=query)
    assert payload["error_code"] == "invalid_input", payload
    assert payload["field"] == "query"
    assert "CHROM-POS-REF-ALT" in payload["message"]
    assert "vep_recode_variant" in payload["recovery"]
    # VEP's recoder does not place a gene-symbol reference, so no ready-to-send call.
    assert [c["tool"] for c in payload["_meta"]["next_commands"]] == ["get_diagnostics"]
    assert stub.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    ["NM_004333.6 c.1799T>A", "NM_004333.6:c.1799T>A p.(Val600Glu)"],
)
async def test_accession_hgvs_with_space_or_protein_tail_sends_the_bare_expression(
    query: str,
) -> None:
    payload, stub = await _call("resolve_variant_id", query=query)
    _assert_converter(
        payload,
        "query",
        {
            "tool": "vep_recode_variant",
            "arguments": {"variants": [HGVS], "fields": "vcf_string", "assembly": "GRCh38"},
        },
    )
    assert stub.calls == []
