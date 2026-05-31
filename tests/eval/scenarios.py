"""Eval scenarios: ordered tool calls, expected trajectories, and correctness checks.

Each :class:`Scenario` is a small, deterministic agent-style trajectory over the
real MCP facade (fed by a canned stub from :mod:`fixtures`). A scenario declares:

* the ordered tool calls to execute (``calls``),
* the expected service-level / tool-level trajectory (``expected_tools`` +
  ``trajectory_mode``) used by the trajectory scorer,
* which tools must carry a ``headline`` (``headline_tools``) and which must echo
  dataset + reference_genome in ``_meta`` (``dataset_scoped_tools``), used by the
  envelope-conformance scorer, and
* a ``correctness`` callable that asserts over the ordered list of returned
  payloads (raises ``AssertionError`` on failure).

The expected-tool sets reflect the CURRENT (pre-Phase-3) facade behaviour, which
the smoke recon in this task verified directly against the real payloads.
"""

from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from tests.eval.fixtures import (
    EvalStubService,
    build_compare_stub,
    build_evidence_stub,
    build_gene_carrier_stub,
    build_gene_variants_stub,
    build_resolve_carrier_stub,
)


class TrajectoryMode(enum.Enum):
    """How the actual called-tool sequence is matched against ``expected_tools``."""

    EXACT = "exact"
    IN_ORDER = "in_order"
    ANY_ORDER = "any_order"


@dataclass
class Scenario:
    """A single deterministic eval trajectory over the MCP facade."""

    name: str
    service_factory: Callable[[], EvalStubService]
    # Ordered (tool_name, arguments) calls to execute against the MCP facade.
    calls: list[tuple[str, dict[str, Any]]]
    # Expected sequence of tool names (the trajectory the LLM is meant to follow).
    expected_tools: tuple[str, ...]
    trajectory_mode: TrajectoryMode
    # Tools whose payload must carry a non-empty top-level ``headline``.
    headline_tools: frozenset[str] = field(default_factory=frozenset)
    # Tools whose ``_meta`` must echo dataset + reference_genome.
    dataset_scoped_tools: frozenset[str] = field(default_factory=frozenset)
    # Asserts over the ordered list of returned payloads. Raises on failure.
    correctness: Callable[[list[dict[str, Any]]], None] = lambda payloads: None


def _is_fraction(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0.0 <= value <= 1.0


# ---------------------------------------------------------------------------
# Correctness checks (one per scenario)
# ---------------------------------------------------------------------------


def _check_gene_carrier(payloads: list[dict[str, Any]]) -> None:
    (p,) = payloads
    assert p.get("error_code") is None, p
    assert p["gene"]["symbol"] == "HFE"
    # Reciprocal of the global carrier frequency must be a positive integer.
    g_one_in = p["global"]["carrier_one_in"]
    assert isinstance(g_one_in, int) and g_one_in > 0, p["global"]
    # Carrier frequency is a probability.
    assert _is_fraction(p["global"]["carrier_frequency"]), p["global"]
    # Populations are sorted highest-carrier first (asj highest in the canned data).
    assert p["populations"][0]["population"] == "asj", p["populations"]
    # Qualifying-variant count is carried through from the service summary.
    assert p["contributing_variants"]["count"] == 523


def _check_compare(payloads: list[dict[str, Any]]) -> None:
    (p,) = payloads
    assert p.get("success") is not False, p
    assert p["variant_id"] == "6-26092913-G-A"
    # Both legs present; this is the r2_1 liftover no-op regression guard.
    assert p["datasets"]["gnomad_r4"]["present"] is True, p["datasets"]
    assert p["datasets"]["gnomad_r2_1"]["present"] is True, p["datasets"]
    # r2_1 leg used the lifted GRCh37 source coordinate, not the GRCh38 input.
    assert p["datasets"]["gnomad_r2_1"]["lifted_variant_id"] == "6-26093141-G-A", p["datasets"]
    overall = p["comparison"]["overall_af_by_dataset"]
    assert set(overall) == {"gnomad_r4", "gnomad_r2_1"}, overall
    for af in overall.values():
        assert _is_fraction(af), overall


def _check_evidence(payloads: list[dict[str, Any]]) -> None:
    mito, clinvar = payloads
    # Mitochondrial evidence: ploidy + heteroplasmy present, no verdict.
    assert mito.get("error_code") is None, mito
    assert mito["variant_id"] == "M-3243-A-G"
    assert mito.get("ac_het") == 5 and mito.get("ac_hom") == 0, mito
    assert "heteroplasmy_distribution" in mito, mito
    # ClinVar evidence: submission aggregate present, NOT a pathogenicity verdict.
    assert clinvar.get("error_code") is None, clinvar
    summary = clinvar.get("summary") or {}
    assert summary.get("total") == 6, summary
    assert summary.get("pathogenic") == 2, summary
    assert "conflict" in summary, summary
    # Raw submissions are surfaced as evidence (the tool aggregates, it does not rule).
    assert isinstance(clinvar.get("submissions"), list) and clinvar["submissions"], clinvar
    # The tool must not synthesise a single overall verdict field beyond echoing
    # the upstream clinical_significance string.
    assert "verdict" not in clinvar and "is_pathogenic" not in clinvar, clinvar


def _check_resolve_carrier(payloads: list[dict[str, Any]]) -> None:
    resolve, carrier = payloads
    # Resolution returns the canonical id (enriched with gene/consequence/AF).
    assert resolve.get("success") is not False, resolve
    assert resolve["returned"] == 1, resolve
    first = resolve["results"][0]
    assert first["variant_id"] == "X-153296777-C-T", first
    assert first.get("gene_symbol") == "G6PD", first
    # XL carrier estimate present and plausible (fractions in [0, 1]); do NOT
    # hard-code an exact upstream value -- assert the field exists and is sane.
    assert carrier.get("error_code") is None, carrier
    assert carrier["inheritance"] == "XL", carrier
    overall = carrier["overall"]
    female = overall.get("female_carrier_frequency")
    male = overall.get("affected_male_frequency")
    assert female is not None and _is_fraction(female), overall
    assert male is not None and _is_fraction(male), overall
    # Per-population XL estimates derive from sex-split ancestry rows.
    by_pop = {row["population"]: row for row in carrier.get("per_population", [])}
    assert "nfe" in by_pop, carrier.get("per_population")
    assert _is_fraction(by_pop["nfe"]["female_carrier_frequency"]), by_pop["nfe"]


def _check_gene_carrier_minimal(payloads: list[dict[str, Any]]) -> None:
    (p,) = payloads
    assert p.get("error_code") is None, p
    # Minimal keeps the global block + a contributing-variant COUNT.
    assert p["gene"]["symbol"] == "HFE", p
    g_one_in = p["global"]["carrier_one_in"]
    assert isinstance(g_one_in, int) and g_one_in > 0, p["global"]
    assert _is_fraction(p["global"]["carrier_frequency"]), p["global"]
    assert p["contributing_variants"]["count"] == 523, p["contributing_variants"]
    # The per-population rows and the contributing list are dropped.
    assert "populations" not in p, p
    assert "top" not in p["contributing_variants"], p["contributing_variants"]
    # truncated block names what was dropped and how to restore it.
    assert p["truncated"]["kind"] == "minimal_mode", p["truncated"]
    assert p["truncated"]["to_restore"] == "response_mode='compact'", p["truncated"]


def _check_compare_minimal(payloads: list[dict[str, Any]]) -> None:
    (p,) = payloads
    assert p.get("success") is not False, p
    assert p["variant_id"] == "6-26092913-G-A", p
    # Minimal keeps per-dataset present flags + the global AF per dataset.
    assert p["datasets"]["gnomad_r4"]["present"] is True, p["datasets"]
    assert p["datasets"]["gnomad_r2_1"]["present"] is True, p["datasets"]
    overall = p["comparison"]["overall_af_by_dataset"]
    assert set(overall) == {"gnomad_r4", "gnomad_r2_1"}, overall
    for af in overall.values():
        assert _is_fraction(af), overall
    # The per-population deltas and raw per-dataset rows are dropped.
    assert "per_population_af_deltas" not in p["comparison"], p["comparison"]
    assert "exome" not in p["datasets"]["gnomad_r4"], p["datasets"]["gnomad_r4"]
    assert p["truncated"]["kind"] == "minimal_mode", p["truncated"]
    assert p["truncated"]["to_restore"] == "response_mode='compact'", p["truncated"]


def _check_gene_variants(payloads: list[dict[str, Any]]) -> None:
    (p,) = payloads
    assert p.get("error_code") is None, p
    # Only the stop_gained subset is returned; the canned gene has 2 of 4 rows.
    assert p["total_seen"] == 4, p
    assert p["returned"] == 2, p
    returned_ids = {v["variant_id"] for v in p["variants"]}
    assert returned_ids == {"12-1-A-T", "12-3-A-T"}, returned_ids
    for variant in p["variants"]:
        consequence = variant.get("consequence") or variant.get("major_consequence")
        assert consequence == "stop_gained", variant


# ---------------------------------------------------------------------------
# Scenario registry
# ---------------------------------------------------------------------------


SCENARIOS: list[Scenario] = [
    Scenario(
        name="gene_carrier_frequency_hfe",
        service_factory=build_gene_carrier_stub,
        calls=[("compute_gene_carrier_frequency", {"gene_symbol": "HFE"})],
        expected_tools=("compute_gene_carrier_frequency",),
        trajectory_mode=TrajectoryMode.EXACT,
        headline_tools=frozenset({"compute_gene_carrier_frequency"}),
        dataset_scoped_tools=frozenset({"compute_gene_carrier_frequency"}),
        correctness=_check_gene_carrier,
    ),
    Scenario(
        name="compare_variant_across_datasets_r4_r2_1",
        service_factory=build_compare_stub,
        calls=[
            (
                "compare_variant_across_datasets",
                {
                    "variant_id": "6-26092913-G-A",
                    "datasets": ["gnomad_r4", "gnomad_r2_1"],
                    "auto_liftover": True,
                },
            )
        ],
        expected_tools=("compare_variant_across_datasets",),
        trajectory_mode=TrajectoryMode.EXACT,
        headline_tools=frozenset({"compare_variant_across_datasets"}),
        dataset_scoped_tools=frozenset(),
        correctness=_check_compare,
    ),
    Scenario(
        name="variant_clinical_evidence",
        service_factory=build_evidence_stub,
        calls=[
            ("get_mitochondrial_variant", {"variant_id": "M-3243-A-G", "dataset": "gnomad_r4"}),
            (
                "get_clinvar_variant_details",
                {"variant_id": "1-55051215-G-GA", "reference_genome": "GRCh38"},
            ),
        ],
        expected_tools=("get_mitochondrial_variant", "get_clinvar_variant_details"),
        trajectory_mode=TrajectoryMode.IN_ORDER,
        headline_tools=frozenset({"get_mitochondrial_variant"}),
        dataset_scoped_tools=frozenset({"get_mitochondrial_variant"}),
        correctness=_check_evidence,
    ),
    Scenario(
        name="resolve_then_xl_carrier_frequency",
        service_factory=build_resolve_carrier_stub,
        calls=[
            ("resolve_variant_id", {"query": "rs1050828", "dataset": "gnomad_r4"}),
            (
                "compute_carrier_frequency",
                {
                    "variant_id": "X-153296777-C-T",
                    "inheritance": "XL",
                    "dataset": "gnomad_r4",
                },
            ),
        ],
        expected_tools=("resolve_variant_id", "compute_carrier_frequency"),
        trajectory_mode=TrajectoryMode.IN_ORDER,
        headline_tools=frozenset({"compute_carrier_frequency"}),
        dataset_scoped_tools=frozenset({"compute_carrier_frequency"}),
        correctness=_check_resolve_carrier,
    ),
    Scenario(
        name="gene_variants_stop_gained",
        service_factory=build_gene_variants_stub,
        calls=[
            (
                "get_gene_variants",
                {"gene_id": "ENSG00000273079", "consequence": "stop_gained"},
            )
        ],
        expected_tools=("get_gene_variants",),
        trajectory_mode=TrajectoryMode.EXACT,
        headline_tools=frozenset(),
        dataset_scoped_tools=frozenset({"get_gene_variants"}),
        correctness=_check_gene_variants,
    ),
    Scenario(
        name="gene_carrier_frequency_hfe_minimal",
        service_factory=build_gene_carrier_stub,
        calls=[
            (
                "compute_gene_carrier_frequency",
                {"gene_symbol": "HFE", "response_mode": "minimal"},
            )
        ],
        expected_tools=("compute_gene_carrier_frequency",),
        trajectory_mode=TrajectoryMode.EXACT,
        headline_tools=frozenset({"compute_gene_carrier_frequency"}),
        dataset_scoped_tools=frozenset({"compute_gene_carrier_frequency"}),
        correctness=_check_gene_carrier_minimal,
    ),
    Scenario(
        name="compare_variant_across_datasets_minimal",
        service_factory=build_compare_stub,
        calls=[
            (
                "compare_variant_across_datasets",
                {
                    "variant_id": "6-26092913-G-A",
                    "datasets": ["gnomad_r4", "gnomad_r2_1"],
                    "auto_liftover": True,
                    "response_mode": "minimal",
                },
            )
        ],
        expected_tools=("compare_variant_across_datasets",),
        trajectory_mode=TrajectoryMode.EXACT,
        headline_tools=frozenset({"compare_variant_across_datasets"}),
        dataset_scoped_tools=frozenset(),
        correctness=_check_compare_minimal,
    ),
]
