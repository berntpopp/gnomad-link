"""Deterministic MCP eval baseline: trajectory, token cost, envelope conformance.

This module runs the five eval scenarios in-process against the real MCP facade
(fed by canned stubs), scores three dimensions, aggregates into a Scorecard, and
asserts no regression against a committed baseline.

It is intentionally network-free and is wired through ``tests/eval`` (NOT
``tests/unit``), so ``make test`` (unit-only) does not run it, but ``make
ci-local``'s format-check + lint DO cover it. Run it explicitly with
``uv run pytest tests/eval -v``.

Baseline lifecycle:
  * First run (no ``baseline.json``): the current scorecard is WRITTEN to
    ``baseline.json`` (including per-scenario byte budgets) and the test passes.
  * Later runs: assert ``scorecard.total >= baseline.total`` (no regression) and
    that every scenario's correctness check passed.
  * Set ``EVAL_UPDATE_BASELINE=1`` to intentionally overwrite the baseline (e.g.
    after a phase deliberately changes behaviour).

Envelope conformance is NOT asserted to be 10 here: the baseline captures the
current pre-Phase-3 value, which later phases improve.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from gnomad_link.mcp.facade import create_gnomad_mcp
from tests.eval.scenarios import SCENARIOS, Scenario
from tests.eval.scoring import (
    Scorecard,
    aggregate,
    score_envelope_conformance,
    score_token_cost,
    score_trajectory,
)

_BASELINE_PATH = Path(__file__).with_name("baseline.json")
_REGRESSION_EPSILON = 1e-6


async def _run_scenario(scenario: Scenario, budgets: list[int] | None) -> dict[str, Any]:
    """Execute one scenario end-to-end and return its per-dimension scores.

    Builds a fresh stub + MCP facade, runs the ordered tool calls collecting both
    the returned payloads and the actual called-tool sequence, runs the scenario's
    correctness check (raises on failure), and computes the three dimension scores.
    """
    stub = scenario.service_factory()
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    payloads: list[dict[str, Any]] = []
    actual_tool_names: list[str] = []
    for tool_name, arguments in scenario.calls:
        result = await mcp.call_tool(tool_name, arguments)
        payload = result.structured_content or {}
        payloads.append(payload)
        actual_tool_names.append(tool_name)

    # Correctness gate: raises AssertionError if the scenario is wrong.
    scenario.correctness(payloads)

    trajectory = score_trajectory(actual_tool_names, scenario)
    token_cost, measured_bytes = score_token_cost(payloads, budgets)
    envelope_scores = [
        score_envelope_conformance(payload, tool_name, scenario)
        for payload, (tool_name, _) in zip(payloads, scenario.calls, strict=True)
    ]
    envelope = sum(envelope_scores) / len(envelope_scores) if envelope_scores else 10.0

    return {
        "trajectory": trajectory,
        "token_cost": token_cost,
        "envelope_conformance": envelope,
        "measured_bytes": measured_bytes,
    }


async def _build_scorecard(baseline: dict[str, Any] | None) -> Scorecard:
    budgets_by_scenario: dict[str, list[int]] = {}
    if baseline is not None:
        budgets_by_scenario = {
            name: list(byte_list)
            for name, byte_list in (baseline.get("measured_bytes") or {}).items()
        }
    per_scenario: dict[str, dict[str, Any]] = {}
    for scenario in SCENARIOS:
        budgets = budgets_by_scenario.get(scenario.name)
        per_scenario[scenario.name] = await _run_scenario(scenario, budgets)
    return aggregate(per_scenario)


def _load_baseline() -> dict[str, Any] | None:
    if not _BASELINE_PATH.exists():
        return None
    return json.loads(_BASELINE_PATH.read_text(encoding="ascii"))


def _write_baseline(scorecard: Scorecard) -> None:
    _BASELINE_PATH.write_text(
        json.dumps(scorecard.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )


@pytest.mark.asyncio
async def test_eval_baseline_no_regression() -> None:
    update_requested = os.environ.get("EVAL_UPDATE_BASELINE") == "1"
    baseline = None if update_requested else _load_baseline()

    scorecard = await _build_scorecard(baseline)

    if baseline is None:
        # First run (or explicit refresh): persist the current scorecard as the
        # committed baseline, including per-scenario byte budgets, and pass.
        _write_baseline(scorecard)
        return

    assert scorecard.total >= baseline["total"] - _REGRESSION_EPSILON, (
        f"eval total regressed: {scorecard.total} < baseline {baseline['total']}"
    )
    assert scorecard.trajectory >= baseline["trajectory"] - _REGRESSION_EPSILON, (
        f"eval trajectory regressed: {scorecard.trajectory} < baseline {baseline['trajectory']}"
    )
    assert scorecard.token_cost >= baseline["token_cost"] - _REGRESSION_EPSILON, (
        f"eval token_cost regressed: {scorecard.token_cost} < baseline {baseline['token_cost']}"
    )
    assert (
        scorecard.envelope_conformance >= baseline["envelope_conformance"] - _REGRESSION_EPSILON
    ), (
        f"eval envelope_conformance regressed: "
        f"{scorecard.envelope_conformance} < baseline {baseline['envelope_conformance']}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
async def test_scenario_correctness(scenario: Scenario) -> None:
    """Each scenario's correctness check must pass independently of scoring."""
    stub = scenario.service_factory()
    mcp = create_gnomad_mcp(service_factory=lambda: stub)
    payloads: list[dict[str, Any]] = []
    for tool_name, arguments in scenario.calls:
        result = await mcp.call_tool(tool_name, arguments)
        payloads.append(result.structured_content or {})
    scenario.correctness(payloads)
