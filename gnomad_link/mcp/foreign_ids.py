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
from gnomad_link.mcp.patterns import as_mito_variant_id

GENE_FORMS = ["gene symbol (e.g. KRAS)", "Ensembl gene id (e.g. ENSG00000133703)"]
VARIANT_FORMS = [
    "CHROM-POS-REF-ALT (e.g. 12-25245350-C-T)",
    "dbSNP rsID (e.g. rs121913529)",
    "mitochondrial M-POS-REF-ALT (e.g. M-3243-A-G)",
]

# Matched values are echoed into next_commands, so every pattern is ASCII-only
# (no non-Latin digits, bidi or zero-width characters) and length-capped.
# UniProt accessions are not detected: real symbols share the shape (P2RY12).
_FLAGS = re.IGNORECASE | re.ASCII
_HGNC_CONVERTIBLE = re.compile(r"HGNC:\d{1,9}|[NX][MRP]_\d{6,12}(\.\d{1,3})?", _FLAGS)
_NCBI_GENE = re.compile(r"(?:NCBIGene:)?(\d{1,12})", _FLAGS)
_ENST = re.compile(r"ENST\d{11}(\.\d{1,3})?", _FLAGS)
# HGVS: an optional reference (":" or space, as in "PTEN c.-72C>T"), a c./g./m./n./p./r.
# description that starts like one, and an optional protein tail (" p.(Leu76del)").
_HGVS = re.compile(
    r"(?:(?P<ref>[A-Za-z0-9_.()-]{1,40})(?::| +))?"
    r"(?P<desc>(?:[cgmnr]\.[0-9(*=?-]|p\.[A-Za-z(*=?])[A-Za-z0-9_>=?*+()\[\];-]{0,80})"
    r"(?: +\(?p\.[A-Za-z0-9_>=?*+()\[\];-]{1,80})?",
    re.ASCII,
)
# References a recoder can place: RefSeq / LRG / Ensembl accessions or a chromosome.
_HGVS_REFERENCE = re.compile(
    r"[NX][CGMRTW]_\d{1,12}(\.\d{1,3})?(\([A-Za-z0-9_.-]{1,20}\))?|LRG_\d{1,6}(t\d{1,3})?"
    r"|ENS[TG]\d{11}(\.\d{1,3})?|(chr)?([1-9]|1\d|2[0-2]|X|Y)",
    _FLAGS,
)
# Near-miss coordinate ids: chr prefix, lower case, ":" / space / ">" / "/" separators.
_LOOSE_ID = re.compile(
    r"(?:chr)?([1-9]|1\d|2[0-2]|X|Y)[-:_ ](\d{1,9})[-:_ ]([ACGT]{1,50})[-:_ />]{1,3}([ACGT]{1,50})",
    _FLAGS,
)
# A deletion written with an empty alt ("12-102843751-AGA-"): not VCF left-anchored.
_EMPTY_ALT = re.compile(
    r"(?:chr)?([1-9]|1\d|2[0-2]|X|Y)[-:](\d{1,9})[-:]([ACGT]{1,50})[-:][-.]?", _FLAGS
)
_AUTOSOME_GRAMMAR = r"[1-9]|1\d|2[0-2]|X|Y"
_PRINTABLE = re.compile(r"[ -~]{3,100}")  # resolve_variant_id's query bounds, ASCII only
_MITO_SNV = re.compile(r"(?:[A-Za-z0-9_.]{1,20}:)?m\.(\d{1,5})([ACGT])>([ACGT])", re.ASCII)


def foreign_recovery(
    value: object, kind: Literal["gene", "variant"], dataset: str | None = None
) -> dict[str, Any] | None:
    """Recovery for a well-formed id in a namespace we do not take; None if it is ours."""
    if not isinstance(value, str):
        return None
    v = value.strip()
    if kind == "variant":
        hgvs = _HGVS.fullmatch(v)
        if not hgvs:
            return None
        found: dict[str, Any] = {
            "message": "This is an HGVS expression; gnomAD does not convert HGVS. "
            "It takes CHROM-POS-REF-ALT or an rsID.",
            "allowed_values": VARIANT_FORMS,
            # VEP's recoder does not place a gene-symbol reference (PTEN:c.-72C>T), so no call.
            "recovery": "Not a retry: write the change on its transcript accession "
            "(e.g. NM_004333.6:c.1799T>A, not BRAF c.1799T>A), call vep_recode_variant with "
            "it and pass its vcf_string, which is the CHROM-POS-REF-ALT id, to this tool.",
            "command": None,
        }
        if hgvs["desc"].startswith("m."):
            found["message"] = "This is a mitochondrial HGVS expression (m.)."
            found["recovery"] = (
                "Not a retry: call get_mitochondrial_variant with the M-POS-REF-ALT form "
                "(m.3243A>G is M-3243-A-G)."
            )
            if snv := _MITO_SNV.fullmatch(hgvs["desc"]):
                found["command"] = cmd(
                    "get_mitochondrial_variant", variant_id="M-{}-{}-{}".format(*snv.groups())
                )
        elif _HGVS_REFERENCE.fullmatch(hgvs["ref"] or ""):
            expr = f"{hgvs['ref']}:{hgvs['desc']}"  # canonical form, protein tail dropped
            args: dict[str, Any] = {"variants": [expr], "fields": "vcf_string"}
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


def malformed_variant_recovery(value: object) -> dict[str, Any]:
    """Recovery for a variant id of no recognised form: the accepted form and the next call."""
    # A bare rs number may arrive as a JSON integer, failing the str type check.
    v = str(value).strip() if isinstance(value, str) or type(value) is int else ""
    recovery = (
        "Not a retry: send CHROM-POS-REF-ALT (VCF-style, left-anchored indels, e.g. "
        "17-7674232-G-A or 1-55051214-AG-A) or call the next command to find it."
    )
    command = None
    if v.isascii() and v.isdigit():
        command = cmd("resolve_variant_id", query=f"rs{v}")
    elif m := _LOOSE_ID.fullmatch(v):
        command = cmd("resolve_variant_id", query="-".join(m.groups()).upper())
    elif m := _EMPTY_ALT.fullmatch(v):
        chrom, pos, ref = m[1].upper(), int(m[2]), m[3]
        span = f"{pos}_{pos + len(ref) - 1}" if len(ref) > 1 else str(pos)
        command = cmd("vep_recode_variant", variants=[f"{chrom}:g.{span}del"], fields="vcf_string")
        recovery = (
            "Not a retry: an empty ALT is not a gnomAD id (indels keep the preceding base). "
            "Call vep_recode_variant and pass its vcf_string, the CHROM-POS-REF-ALT id, to this tool."
        )
    elif _PRINTABLE.fullmatch(v):
        command = cmd("resolve_variant_id", query=v)
    return {
        "message": "Not a gnomAD variant id: it takes CHROM-POS-REF-ALT (e.g. 17-7674232-G-A).",
        "allowed_values": VARIANT_FORMS,
        "recovery": recovery,
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
        value = err.get("input")
        if "variant" not in field or as_mito_variant_id(value):
            continue
        # Only the CHROM-POS-REF-ALT grammars (all start with the autosome alternation) get
        # the malformed hint; SV / mito ids are not resolve_variant_id's to answer.
        grammar = str((err.get("ctx") or {}).get("pattern", ""))
        ours = grammar.lstrip("^(").startswith(_AUTOSOME_GRAMMAR) or type(value) is int
        found = foreign_recovery(value, "variant") or (
            malformed_variant_recovery(value) if ours else None
        )
        if found:
            _apply(payload, found, field)
            return
