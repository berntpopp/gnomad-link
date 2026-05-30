"""Task B3: ClinVar submissions aggregate into a structured pathogenic/benign summary.

`summarize_clinvar_submissions` groups raw submissions into the canonical
ClinVar buckets (pathogenic, likely_pathogenic, uncertain, likely_benign,
benign, other), flags `conflict` when both pathogenic-side and benign-side
reviewers are present, and reports `total` from the FULL input. The facade
must compute this BEFORE truncation so a capped response still reports
accurate aggregates.
"""

from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.models import ClinVarSubmission, ClinVarVariant


def test_summary_counts_classifications_correctly() -> None:
    from gnomad_link.mcp.shaping import summarize_clinvar_submissions

    submissions: list[dict[str, Any]] = [
        {"clinical_significance": "Pathogenic"},
        {"clinical_significance": "Pathogenic"},
        {"clinical_significance": "Likely pathogenic"},
        {"clinical_significance": "Uncertain significance"},
        {"clinical_significance": "Benign"},
        {"clinical_significance": "Likely benign"},
        {"clinical_significance": "Drug response"},
        {"clinical_significance": None},
    ]

    summary = summarize_clinvar_submissions(submissions)

    assert summary == {
        "pathogenic": 2,
        "likely_pathogenic": 1,
        "uncertain": 1,
        "conflicting": 0,
        "likely_benign": 1,
        "benign": 1,
        "other": 2,
        "conflict": True,
        "total": 8,
    }


def test_conflicting_classification_not_counted_pathogenic() -> None:
    """ "Conflicting classifications of pathogenicity" lands in its own bucket.

    It contains the "pathogenic" substring, so a naive `"pathogenic" in s` test
    would over-count it as pathogenic. It must not inflate the pathogenic side
    nor (on its own) trip the pathogenic-vs-benign `conflict` flag.
    """
    from gnomad_link.mcp.shaping import summarize_clinvar_submissions

    submissions: list[dict[str, Any]] = [
        {"clinical_significance": "Conflicting classifications of pathogenicity"},
        {"clinical_significance": "Conflicting classifications of pathogenicity"},
        {"clinical_significance": "Uncertain significance"},
    ]

    summary = summarize_clinvar_submissions(submissions)

    assert summary["conflicting"] == 2
    assert summary["pathogenic"] == 0
    assert summary["likely_pathogenic"] == 0
    assert summary["conflict"] is False
    assert summary["total"] == 3


def test_summary_no_conflict_when_only_pathogenic() -> None:
    from gnomad_link.mcp.shaping import summarize_clinvar_submissions

    submissions: list[dict[str, Any]] = [
        {"clinical_significance": "Pathogenic"},
        {"clinical_significance": "Pathogenic"},
        {"clinical_significance": "Likely pathogenic"},
    ]

    summary = summarize_clinvar_submissions(submissions)

    assert summary["conflict"] is False
    assert summary["pathogenic"] == 2
    assert summary["likely_pathogenic"] == 1
    assert summary["total"] == 3


def test_summary_no_conflict_when_only_benign() -> None:
    from gnomad_link.mcp.shaping import summarize_clinvar_submissions

    submissions: list[dict[str, Any]] = [
        {"clinical_significance": "Benign"},
        {"clinical_significance": "Likely benign"},
        {"clinical_significance": "Benign"},
    ]

    summary = summarize_clinvar_submissions(submissions)

    assert summary["conflict"] is False
    assert summary["benign"] == 2
    assert summary["likely_benign"] == 1
    assert summary["total"] == 3


def test_summary_no_conflict_when_only_uncertain() -> None:
    from gnomad_link.mcp.shaping import summarize_clinvar_submissions

    submissions: list[dict[str, Any]] = [
        {"clinical_significance": "Uncertain significance"},
        {"clinical_significance": "Uncertain significance"},
    ]

    summary = summarize_clinvar_submissions(submissions)

    assert summary["conflict"] is False
    assert summary["uncertain"] == 2
    assert summary["total"] == 2


def test_summary_empty_submissions() -> None:
    from gnomad_link.mcp.shaping import summarize_clinvar_submissions

    summary = summarize_clinvar_submissions([])

    assert summary == {
        "pathogenic": 0,
        "likely_pathogenic": 0,
        "uncertain": 0,
        "conflicting": 0,
        "likely_benign": 0,
        "benign": 0,
        "other": 0,
        "conflict": False,
        "total": 0,
    }


class _ClinVarStubService:
    """Minimal FrequencyService stub that returns a fixed ClinVarVariant."""

    def __init__(self, variant: ClinVarVariant) -> None:
        self._variant = variant

    async def get_clinvar_variant(self, variant_id: str, reference_genome: str) -> ClinVarVariant:
        return self._variant


def _build_variant(submissions: list[dict[str, Any]]) -> ClinVarVariant:
    return ClinVarVariant(
        variant_id="1-55051215-G-GA",
        reference_genome="GRCh38",
        chrom="1",
        pos=55051215,
        ref="G",
        alt="GA",
        clinical_significance="Pathogenic",
        clinvar_variation_id="12345",
        gnomad=None,
        gold_stars=2,
        in_gnomad=True,
        last_evaluated=None,
        review_status="criteria provided, multiple submitters, no conflicts",
        rsid=None,
        submissions=[ClinVarSubmission(**s) for s in submissions],
    )


@pytest.mark.asyncio
async def test_get_clinvar_variant_details_emits_summary_via_facade() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    submissions = [
        {"clinical_significance": "Pathogenic"},
        {"clinical_significance": "Pathogenic"},
        {"clinical_significance": "Likely pathogenic"},
        {"clinical_significance": "Uncertain significance"},
        {"clinical_significance": "Benign"},
        {"clinical_significance": "Likely benign"},
        {"clinical_significance": "Drug response"},
        {"clinical_significance": None},
    ]
    variant = _build_variant(submissions)
    mcp = create_gnomad_mcp(service_factory=lambda: _ClinVarStubService(variant))

    result = await mcp.call_tool(
        "get_clinvar_variant_details",
        {"variant_id": "1-55051215-G-GA", "reference_genome": "GRCh38"},
    )
    payload = result.structured_content or {}

    assert payload.get("error_code") != "validation_failed", payload
    summary = payload.get("summary")
    assert summary == {
        "pathogenic": 2,
        "likely_pathogenic": 1,
        "uncertain": 1,
        "conflicting": 0,
        "likely_benign": 1,
        "benign": 1,
        "other": 2,
        "conflict": True,
        "total": 8,
    }


@pytest.mark.asyncio
async def test_summary_total_reflects_full_input_even_when_truncated() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    # 30 mixed entries: 10 pathogenic + 10 benign + 10 uncertain.
    submissions: list[dict[str, Any]] = (
        [{"clinical_significance": "Pathogenic"} for _ in range(10)]
        + [{"clinical_significance": "Benign"} for _ in range(10)]
        + [{"clinical_significance": "Uncertain significance"} for _ in range(10)]
    )
    variant = _build_variant(submissions)
    mcp = create_gnomad_mcp(service_factory=lambda: _ClinVarStubService(variant))

    result = await mcp.call_tool(
        "get_clinvar_variant_details",
        {
            "variant_id": "1-55051215-G-GA",
            "reference_genome": "GRCh38",
            "submissions_limit": 5,
        },
    )
    payload = result.structured_content or {}

    assert payload.get("error_code") != "validation_failed", payload
    summary = payload.get("summary") or {}
    # Total must reflect FULL input, not the capped slice.
    assert summary.get("total") == 30
    assert summary.get("pathogenic") == 10
    assert summary.get("benign") == 10
    assert summary.get("uncertain") == 10
    assert summary.get("conflict") is True
    # Submissions list must be capped, with a truncated block reporting drop count.
    assert len(payload.get("submissions") or []) == 5
    trunc = payload.get("truncated") or {}
    assert trunc.get("kind") == "submissions"
    assert trunc.get("dropped") == 25
