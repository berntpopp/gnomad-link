"""Fence ClinVar submitter-authored prose as v1.1 untrusted_text at the MCP boundary.

`ClinVarCondition.name` and `ClinVarSubmission.submitter_name`
(`gnomad_link.models.clinvar_models`) are upstream ClinVar submitter-authored
free text, surfaced verbatim through gnomAD's `clinvar_variant` GraphQL
passthrough (`get_clinvar_variant_details`). The internal models keep bare
`str`/`str | None` fields for parsing the upstream response; this module is
the MCP-facing parallel layer (mirrors `pubtator_link`'s `model_dump_mcp()`
pattern) that types those two fields as `UntrustedText` for the public tool
output. It lives in `gnomad_link.mcp` (not `gnomad_link.models`) because
`gnomad_link.mcp.__init__` eagerly builds the tool facade -- importing
`gnomad_link.mcp.untrusted_content` from inside `gnomad_link.models` would
recurse back into the still-initializing `models` package.

Frequency/constraint output elsewhere in this server is numeric and untouched;
only this ClinVar passthrough carries upstream prose.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from gnomad_link.mcp.shaping import build_submissions_truncation_block
from gnomad_link.mcp.untrusted_content import (
    UntrustedText,
    enforce_untrusted_text_limits,
    fence_untrusted_text,
)
from gnomad_link.models.clinvar_models import ClinVarVariant, GnomadInClinVar

# get_clinvar_variant_details' real object-count cap: a well-annotated,
# clinically significant variant can carry hundreds of ClinVar submissions,
# each with one or more conditions, comfortably exceeding the v1.1 default
# 128-object ceiling. This ceiling is generous so that scenario never raises;
# the byte-size backstops (2 MiB/object, 8 MiB/total in
# `enforce_untrusted_text_limits`) remain the real DoS backstop, unchanged.
CLINVAR_MAX_FENCED_OBJECTS = 10_000

UNTRUSTED_TEXT_SOURCE = "gnomad:clinvar"


class MCPClinVarCondition(BaseModel):
    """Condition associated with a ClinVar submission, fenced for the MCP boundary."""

    name: UntrustedText = Field(
        ..., description="Condition name (fenced upstream ClinVar submitter prose)"
    )
    medgen_id: str | None = Field(None, description="MedGen identifier")


class MCPClinVarSubmission(BaseModel):
    """Individual ClinVar submission, fenced for the MCP boundary."""

    clinical_significance: str | None = Field(None, description="Clinical significance")
    last_evaluated: str | None = Field(None, description="Last evaluation date")
    review_status: str | None = Field(None, description="Review status")
    submitter_name: UntrustedText | None = Field(
        None, description="Name of submitter (fenced upstream ClinVar submitter prose)"
    )
    conditions: list[MCPClinVarCondition] = Field(
        default_factory=list, description="Associated conditions"
    )


class MCPClinVarVariant(BaseModel):
    """ClinVar variant information, fenced for the MCP boundary (v1.1 untrusted_text)."""

    variant_id: str = Field(..., description="Variant identifier")
    reference_genome: str = Field(..., description="Reference genome")
    chrom: str = Field(..., description="Chromosome")
    pos: int = Field(..., description="Position")
    ref: str = Field(..., description="Reference allele")
    alt: str = Field(..., description="Alternate allele")
    clinical_significance: str | None = Field(None, description="Overall clinical significance")
    clinvar_variation_id: str | None = Field(None, description="ClinVar variation ID")
    gnomad: GnomadInClinVar | None = Field(None, description="gnomAD data")
    gold_stars: int | None = Field(None, description="ClinVar review status stars")
    in_gnomad: bool | None = Field(None, description="Whether variant is in gnomAD")
    last_evaluated: str | None = Field(None, description="Last evaluation date")
    review_status: str | None = Field(None, description="Review status")
    rsid: str | None = Field(None, description="dbSNP rsID")
    submissions: list[MCPClinVarSubmission] = Field(
        default_factory=list, description="Individual submissions"
    )


def _strip_untrusted_bookkeeping(node: Any) -> None:
    """Drop per-object sha256/retrieved_at from every fenced untrusted_text in-place.

    The fenced envelope carries a 64-char ``raw_sha256`` and an ISO ``retrieved_at``
    per condition-name and submitter-name; on a ClinVar-dense variant that is the
    bulk of the payload (defect #45-6). compact mode keeps the fenced ``text`` +
    ``source``/``record_id`` (still self-describing) and drops the integrity
    bookkeeping, which ``response_mode='full'`` retains.
    """
    if isinstance(node, dict):
        if node.get("kind") == "untrusted_text":
            node.pop("raw_sha256", None)
            provenance = node.get("provenance")
            if isinstance(provenance, dict):
                provenance.pop("retrieved_at", None)
        for value in node.values():
            _strip_untrusted_bookkeeping(value)
    elif isinstance(node, list):
        for item in node:
            _strip_untrusted_bookkeeping(item)


def fence_clinvar_variant(
    variant: ClinVarVariant, *, submissions_limit: int, response_mode: str = "compact"
) -> dict[str, Any]:
    """Return `variant`'s MCP payload with condition names/submitter names fenced.

    Fencing and limit enforcement run over the EMITTED submissions only -- the
    first `submissions_limit` (truncation is always head-of-list), which is
    exactly the set the response returns. Enforcing over the full upstream set
    would raise on a large ClinVar record even when the capped response it
    actually emits is small; the v1.1 ceilings must bound the emitted payload,
    not the upstream fetch. `record_id` keys off the emitted index (0..N-1),
    which equals the upstream index for the retained head slice. The truncated
    block is built from the shared `build_submissions_truncation_block` helper
    so its shape stays identical to `shape_clinvar_submissions`.
    """
    total = len(variant.submissions)
    emitted = variant.submissions[:submissions_limit]
    fenced_objects: list[UntrustedText] = []
    fenced_submissions: list[MCPClinVarSubmission] = []
    for i, submission in enumerate(emitted):
        fenced_conditions: list[MCPClinVarCondition] = []
        for j, condition in enumerate(submission.conditions):
            fenced_name = fence_untrusted_text(
                condition.name,
                source=UNTRUSTED_TEXT_SOURCE,
                record_id=f"{variant.variant_id}#submission:{i}#condition:{j}",
            )
            fenced_objects.append(fenced_name)
            fenced_conditions.append(
                MCPClinVarCondition(name=fenced_name, medgen_id=condition.medgen_id)
            )
        fenced_submitter_name: UntrustedText | None = None
        if submission.submitter_name is not None:
            fenced_submitter_name = fence_untrusted_text(
                submission.submitter_name,
                source=UNTRUSTED_TEXT_SOURCE,
                record_id=f"{variant.variant_id}#submission:{i}",
            )
            fenced_objects.append(fenced_submitter_name)
        fenced_submissions.append(
            MCPClinVarSubmission(
                clinical_significance=submission.clinical_significance,
                last_evaluated=submission.last_evaluated,
                review_status=submission.review_status,
                submitter_name=fenced_submitter_name,
                conditions=fenced_conditions,
            )
        )
    enforce_untrusted_text_limits(fenced_objects, max_objects=CLINVAR_MAX_FENCED_OBJECTS)
    fenced_variant = MCPClinVarVariant(
        **variant.model_dump(exclude={"submissions"}),
        submissions=fenced_submissions,
    )
    payload = fenced_variant.model_dump(mode="json")
    if response_mode == "compact":
        _strip_untrusted_bookkeeping(payload.get("submissions"))
    block = build_submissions_truncation_block(total, submissions_limit=submissions_limit)
    if block is not None:
        payload["truncated"] = block
    return payload
