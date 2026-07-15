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
def test_gene_carrier_flags_only_true_reduced_penetrance_plp() -> None:
    result = {
        "gene": {"gene_id": "ENSG00000001626", "symbol": "CFTR"},
        "dataset": "gnomad_r4",
        "reference_genome": "GRCh38",
        "global": {"carrier_frequency": 0.05},
        "populations": {},
        "qualifying_variants": [
            # P/LP with a penetrance qualifier -> flagged.
            {
                "variant_id": "7-117548630-T-G",
                "global_af": 0.0098,
                "clinvar_significance": "Pathogenic/Likely pathogenic; other",
            },
            {
                "variant_id": "7-1-A-T",
                "global_af": 0.006,
                "clinvar_significance": "Pathogenic; risk factor",
            },
            # A clean P/LP allele -> NOT flagged.
            {
                "variant_id": "7-117559590-ATCT-A",
                "global_af": 0.005,
                "clinvar_significance": "Pathogenic",
            },
            # False-positive guards: none of these are reduced-penetrance P/LP.
            {"variant_id": "7-2-A-T", "global_af": 0.004, "clinvar_significance": "Benign"},
            {
                "variant_id": "7-3-A-T",
                "global_af": 0.003,
                "clinvar_significance": "Uncertain significance",
            },
            {
                "variant_id": "7-4-A-T",
                "global_af": 0.002,
                "clinvar_significance": "Conflicting classifications of pathogenicity",
            },
        ],
        "qualifying_count": 6,
    }
    shaped = shape_gene_carrier(result, response_mode="full", top_variants_limit=25)

    top = shaped["contributing_variants"]["top"]
    flagged = {v["variant_id"] for v in top if v.get("penetrance_flag") == "reduced_or_variable"}
    assert flagged == {"7-117548630-T-G", "7-1-A-T"}
    for vid in ("7-117559590-ATCT-A", "7-2-A-T", "7-3-A-T", "7-4-A-T"):
        v = next(x for x in top if x["variant_id"] == vid)
        assert "penetrance_flag" not in v, f"{vid} must not be flagged reduced-penetrance"

    assert shaped["contributing_variants"]["reduced_penetrance_variants"] == 2
    assert "reduced-penetrance" in shaped["assumptions_note"].lower()


# (d) the populations filter is a closed vocabulary: a bogus code is rejected,
#     never silently matched to nothing.
@pytest.mark.asyncio
async def test_out_of_vocab_population_is_rejected_not_silently_zeroed() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: object())
    for tool, args in (
        ("get_variant_frequencies", {"variant_id": "1-55051215-G-GA", "populations": ["__nope__"]}),
        ("get_variant_details", {"variant_id": "1-55051215-G-GA", "populations": ["afr", "__x__"]}),
        (
            "compare_variant_across_datasets",
            {"variant_id": "1-55039974-G-T", "populations": ["__nope__"]},
        ),
    ):
        result = await mcp.call_tool(tool, args)
        env = result.structured_content or {}
        assert env.get("error_code") == "invalid_input", (tool, env)
        assert result.is_error is True, tool


# (e) a coordinate-SHAPED but invalid target is rejected, never reinterpreted as a
#     gene symbol (the silently-empty filter re-introduced by the target collapse).
@pytest.mark.asyncio
async def test_region_shaped_but_invalid_target_is_rejected_not_a_gene_query() -> None:
    mcp = create_gnomad_mcp(service_factory=lambda: object())
    for tool in ("search_structural_variants", "get_coverage"):
        result = await mcp.call_tool(tool, {"target": "MT-1-200"})
        env = result.structured_content or {}
        assert env.get("error_code") == "invalid_input", (tool, env)
        assert result.is_error is True, tool
        assert "region-shaped" in str(env.get("message", "")).lower()


# (f) the search resolvers report an honest total_count / has_more (invariant under
#     limit): 5 candidates at limit=1 must not look like 1.
class _MultiCandidateService:
    _IDS = [f"1-{1000 + i}-A-G" for i in range(5)]

    async def search_variants(self, query: str, dataset: str) -> list[str]:
        return list(self._IDS)


@pytest.mark.asyncio
async def test_search_resolver_reports_honest_has_more() -> None:
    mcp = create_gnomad_mcp(service_factory=_MultiCandidateService)
    one = (
        await mcp.call_tool("resolve_variant_id", {"query": "rs1", "limit": 1, "enrich": False})
    ).structured_content or {}
    assert one["returned"] == 1
    assert one["total_count"] == 5, "total must be the candidate count, not the page"
    assert one["has_more"] is True

    three = (
        await mcp.call_tool("resolve_variant_id", {"query": "rs1", "limit": 3, "enrich": False})
    ).structured_content or {}
    assert three["returned"] == 3
    assert three["total_count"] == 5
    assert three["has_more"] is True
