"""Regression tests for the MCP contract-hardening pass (issue #45, v9.0.0).

Three defects the pre-fix code shipped green:
  (a) rows dropped at the limit while the reported total was the PAGE size, so an
      agent concluded it had seen everything (lying total / truncated).
  (b) an out-of-vocabulary `consequence` / `sv_type` returned success:true with 0
      rows -- the silently-empty filter -- instead of an actionable error.
  (c) reduced/variable-penetrance ClinVar alleles were summed at full weight with
      no flag and no caveat, overstating carrier frequency (CFTR is the canonical
      case).
"""

from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.mcp.facade import create_gnomad_mcp
from gnomad_link.mcp.gene_carrier_shaping import shape_gene_carrier
from gnomad_link.mcp.shaping import shape_gene_variants


def _raw_variants(n: int) -> list[dict[str, Any]]:
    return [
        {
            "variant_id": f"1-{1000 + i}-A-G",
            "major_consequence": "missense_variant",
            "af": 0.001,
            "ac": 5,
            "an": 30000,
        }
        for i in range(n)
    ]


# (a) honest pagination: total_count is the TRUE total, invariant under limit, and
#     a partial page declares has_more.
def test_gene_variants_total_count_is_honest_and_invariant_under_limit() -> None:
    raw = _raw_variants(50)
    small = shape_gene_variants(
        raw, limit=5, consequence=None, max_af=None, min_ac=None, include_populations=False
    )
    large = shape_gene_variants(
        raw, limit=20, consequence=None, max_af=None, min_ac=None, include_populations=False
    )

    # The page is capped, but the total reflects the whole result set.
    assert small["returned"] == 5
    assert small["total_count"] == 50, "total must be the result-set size, not the page size"
    assert small["has_more"] is True, "a partial page MUST declare has_more"

    # Behaviour-gate B4: total is invariant under limit (it is not tracking the page).
    assert large["total_count"] == 50
    assert large["returned"] == 20
    assert large["has_more"] is True

    # A full page (limit >= total) is honest about there being no more.
    full = shape_gene_variants(
        raw, limit=100, consequence=None, max_af=None, min_ac=None, include_populations=False
    )
    assert full["returned"] == 50
    assert full["total_count"] == 50
    assert full["has_more"] is False


# (b) an out-of-vocabulary filter value is REJECTED (invalid_input), never silently
#     matched to nothing. The Literal enums reject at the argument boundary.
@pytest.mark.asyncio
async def test_out_of_vocab_consequence_is_rejected_not_silently_zeroed() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: object())
    result = await mcp.call_tool(
        "get_gene_variants",
        {"gene_id": "ENSG00000169174", "consequence": "__not_a_real_consequence__"},
    )
    env = result.structured_content or {}
    assert env.get("success") is False, "a bogus consequence must error, not return 0 rows"
    assert env.get("error_code") == "invalid_input"
    assert result.is_error is True


@pytest.mark.asyncio
async def test_out_of_vocab_sv_type_is_rejected_not_silently_zeroed() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: object())
    result = await mcp.call_tool(
        "search_structural_variants",
        {"target": "SMARCA4", "sv_type": "__not_a_real_sv_type__"},
    )
    env = result.structured_content or {}
    assert env.get("success") is False
    assert env.get("error_code") == "invalid_input"
    assert result.is_error is True


# (c) reduced/variable-penetrance alleles are flagged and the assumptions note
#     caveats the known ClinVar-P/LP overestimate.
def test_gene_carrier_flags_reduced_penetrance_and_caveats() -> None:
    result = {
        "gene": {"gene_id": "ENSG00000001626", "symbol": "CFTR"},
        "dataset": "gnomad_r4",
        "reference_genome": "GRCh38",
        "global": {"carrier_frequency": 0.05},
        "populations": {},
        "qualifying_variants": [
            # The 5T/R117H-style allele: P/LP with a trailing qualifier -> flagged.
            {
                "variant_id": "7-117548630-T-G",
                "global_af": 0.0098,
                "clinvar_significance": "Pathogenic/Likely pathogenic; other",
            },
            # A clean P/LP allele -> NOT flagged.
            {
                "variant_id": "7-117559590-ATCT-A",
                "global_af": 0.007,
                "clinvar_significance": "Pathogenic",
            },
        ],
        "qualifying_count": 2,
    }
    shaped = shape_gene_carrier(result, response_mode="compact", top_variants_limit=25)

    top = shaped["contributing_variants"]["top"]
    flagged = [v for v in top if v.get("penetrance_flag") == "reduced_or_variable"]
    assert [v["variant_id"] for v in flagged] == ["7-117548630-T-G"]
    clean = next(v for v in top if v["variant_id"] == "7-117559590-ATCT-A")
    assert "penetrance_flag" not in clean, "a clean P/LP allele must not be flagged"

    assert shaped["contributing_variants"]["reduced_penetrance_variants"] == 1
    assert "reduced-penetrance" in shaped["assumptions_note"].lower()
