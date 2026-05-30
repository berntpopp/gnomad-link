"""M-1: relax_output_schema must nullable-ize bare scalar types so upstream nulls
(BND/CTX/CPX structural variants returning null end/af/pos) pass MCP output-schema
validation — while leaving enum/const assertions intact.
"""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from gnomad_link.mcp.schema_relax import relax_output_schema


def test_bare_scalar_becomes_nullable() -> None:
    relaxed = relax_output_schema({"type": "object", "properties": {"end": {"type": "integer"}}})
    assert relaxed["properties"]["end"]["type"] == ["integer", "null"]


def test_number_token_is_preserved_not_widened() -> None:
    relaxed = relax_output_schema({"type": "object", "properties": {"af": {"type": "number"}}})
    assert relaxed["properties"]["af"]["type"] == ["number", "null"]


def test_enum_node_is_not_nullable_ized() -> None:
    relaxed = relax_output_schema({"type": "string", "enum": ["a", "b"]})
    # null must NOT be added: it would pass `type` but fail the enum assertion.
    assert relaxed["type"] == "string"
    assert relaxed["enum"] == ["a", "b"]


def test_container_types_untouched() -> None:
    relaxed = relax_output_schema(
        {"type": "object", "properties": {"genes": {"type": "array", "items": {"type": "string"}}}}
    )
    assert relaxed["properties"]["genes"]["type"] == "array"
    # the array's string items DO become nullable, but the array itself does not.
    assert relaxed["properties"]["genes"]["items"]["type"] == ["string", "null"]


def test_relaxed_structural_variant_schema_accepts_null_bearing_bnd() -> None:
    from gnomad_link.models import StructuralVariant

    relaxed = relax_output_schema(StructuralVariant.model_json_schema())
    # A breakend/translocation-shaped payload: end/af/pos are null upstream.
    bnd: dict[str, Any] = {
        "variant_id": "BND_chr1_1",
        "reference_genome": "GRCh38",
        "chrom": "1",
        "type": "BND",
        "pos": None,
        "end": None,
        "length": None,
        "ac": None,
        "an": None,
        "af": None,
        "populations": [],
        "consequences": [],
    }
    errors = list(Draft202012Validator(relaxed).iter_errors(bnd))
    assert errors == [], errors


def test_relaxed_gene_search_schema_still_rejects_out_of_enum_match_quality() -> None:
    from gnomad_link.models import GeneSearchResult

    relaxed = relax_output_schema(GeneSearchResult.model_json_schema())
    bad = {"ensembl_id": "ENSG1", "symbol": "X", "match_quality": "not_a_real_value"}
    errors = list(Draft202012Validator(relaxed).iter_errors(bad))
    # The enum branch must survive relaxation.
    assert any("not_a_real_value" in str(e.message) for e in errors), errors
