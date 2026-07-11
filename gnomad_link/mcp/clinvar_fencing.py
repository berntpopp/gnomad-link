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


def fence_clinvar_variant(variant: ClinVarVariant) -> dict[str, Any]:
    """Return `variant`'s MCP payload with condition names/submitter names fenced.

    Every submission's `conditions[].name` and `submitter_name` are fenced --
    not just the (possibly truncated) slice the tool ultimately returns -- so
    each `record_id` stays keyed to the full upstream submission/condition
    index, independent of the caller's `submissions_limit`. Truncation for
    return happens afterward, at the dict level, in
    `gnomad_link.mcp.shaping.shape_clinvar_submissions`.
    """
    fenced_objects: list[UntrustedText] = []
    fenced_submissions: list[MCPClinVarSubmission] = []
    for i, submission in enumerate(variant.submissions):
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
    return fenced_variant.model_dump(mode="json")
