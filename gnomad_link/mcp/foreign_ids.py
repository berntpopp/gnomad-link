"""Identifiers in a namespace these tools do not take: name the converter (router #343).

gnomAD has no cross-reference for these forms, so the answer is an ``invalid_input``
whose first ``_meta.next_commands`` entry is a ready-to-send converter call -- never an
empty success, and never an upstream request.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from gnomad_link.mcp.mito_redirect import redirect_validation_payload as _redirect_mito
from gnomad_link.mcp.next_commands import cmd

GENE_FORMS = ["gene symbol (e.g. KRAS)", "Ensembl gene id (e.g. ENSG00000133703)"]
VARIANT_FORMS = [
    "CHROM-POS-REF-ALT (e.g. 12-25245350-C-T)",
    "dbSNP rsID (e.g. rs121913529)",
    "mitochondrial M-POS-REF-ALT (e.g. M-3243-A-G)",
]

# UniProt accessions are not detected: real symbols share the shape (P2RY12).
_HGNC_CONVERTIBLE = re.compile(r"HGNC:\d+|[NX][MRP]_\d+(\.\d+)?", re.IGNORECASE)
_NCBI_GENE = re.compile(r"(?:NCBIGene:)?(\d+)", re.IGNORECASE)
_ENST = re.compile(r"ENST\d{11}(\.\d+)?", re.IGNORECASE)
# HGVS: an optional reference, then a c./g./m./n./p./r. description.
_HGVS = re.compile(r"(?:\S+:)?[cgmnpr]\.\S+")


def foreign_recovery(
    value: object, kind: Literal["gene", "variant"], dataset: str | None = None
) -> dict[str, Any] | None:
    """Recovery for a well-formed id in a namespace we do not take; None if it is ours."""
    if not isinstance(value, str):
        return None
    v = value.strip()
    if kind == "variant":
        if not _HGVS.fullmatch(v):
            return None
        found: dict[str, Any] = {
            "message": "This is an HGVS expression; gnomAD does not convert HGVS.",
            "allowed_values": VARIANT_FORMS,
            "recovery": "Not a retry: an HGVS expression needs a reference sequence "
            "(e.g. NM_004333.6:c.1799T>A) to be converted to coordinates.",
            "command": None,
        }
        if ":" in v:
            args: dict[str, Any] = {"variants": [v], "fields": "vcf_string"}
            if dataset:
                args["assembly"] = "GRCh37" if dataset == "gnomad_r2_1" else "GRCh38"
            found["command"] = cmd("vep_recode_variant", **args)
            found["recovery"] = (
                "Not a retry: call vep_recode_variant (assembly = the build of your gnomAD "
                "dataset; GRCh37 for gnomad_r2_1) and pass its vcf_string, which is the "
                "CHROM-POS-REF-ALT id, to this tool."
            )
        return found
    if _HGNC_CONVERTIBLE.fullmatch(v):
        command = cmd("hgnc_resolve_symbol", query=v)
        form, via = "an HGNC id or RefSeq accession", "hgnc_resolve_symbol"
    elif m := _NCBI_GENE.fullmatch(v):
        command = cmd("hgnc_resolve_gene_by_xref", source="entrez_id", value=m.group(1))
        form, via = "an NCBI Gene id", "hgnc_resolve_gene_by_xref"
    elif _ENST.fullmatch(v):
        command = cmd("get_transcript_details", transcript_id=v.upper())
        form, via = "an Ensembl transcript id", "get_transcript_details"
    else:
        return None
    return {
        "message": f"This is {form}; gnomAD looks genes up by symbol or Ensembl gene id.",
        "allowed_values": GENE_FORMS,
        "recovery": f"Not a retry: call {via} and pass the gene it returns to this tool.",
        "command": command,
    }


def _apply(payload: dict[str, Any], found: dict[str, Any], field: str) -> None:
    command = found["command"]
    payload["message"], payload["recovery"] = found["message"], found["recovery"]
    payload["field"], payload["allowed_values"] = field, found["allowed_values"]
    if command:
        payload["recovery_action"] = "switch_tool"
        payload["fallback_tool"], payload["fallback_args"] = command["tool"], command["arguments"]
        payload["_meta"]["next_commands"].insert(0, command)


def reject_foreign(
    value: str,
    kind: Literal["gene", "variant"],
    *,
    field: str,
    tool: str,
    dataset: str | None = None,
) -> None:
    """Raise the invalid_input envelope if ``value`` is in a namespace we do not take."""
    found = foreign_recovery(value, kind, dataset)
    if found is None:
        return
    # Imported here: errors imports this module for the validation redirect below.
    from gnomad_link.mcp.errors import McpErrorContext, McpToolError, _provenance_meta

    payload: dict[str, Any] = {
        "success": False,
        "error_code": "invalid_input",
        "retryable": False,
        "recovery_action": "reformulate_input",
        "fallback_tool": "get_diagnostics",
        "fallback_args": {},
        "_meta": {
            "tool": tool,
            "next_commands": [cmd("get_diagnostics")],
            **_provenance_meta(McpErrorContext(tool_name=tool, dataset=dataset)),
        },
    }
    _apply(payload, found, field)
    raise McpToolError(payload)


def redirect_validation_payload(payload: dict[str, Any], errors: list[Any]) -> None:
    """In place: point a schema-validation envelope at the mito tool or the HGVS converter."""
    _redirect_mito(payload, errors)
    for err in errors:
        field = ".".join(str(x) for x in err.get("loc", ()))
        found = foreign_recovery(err.get("input"), "variant") if "variant" in field else None
        if found:
            _apply(payload, found, field)
            return
