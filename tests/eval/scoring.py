"""Scorers for the MCP eval harness: trajectory, token cost, envelope conformance.

Three independent dimensions, each returning a float on a 0..10 scale, plus an
:func:`aggregate` that means them into a :class:`Scorecard`.

WEIGHTING
---------
The three dimensions are weighted EQUALLY: ``total`` is the unweighted mean of
the per-dimension means (trajectory, token_cost, envelope_conformance), kept on
the same 0..10 scale. This is deliberate for the baseline phase -- no dimension
is privileged before later phases tune behaviour. Adjust the weights here (not at
call sites) if a future phase wants to bias the aggregate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tests.eval.scenarios import Scenario

_MAX_SCORE = 10.0


# ---------------------------------------------------------------------------
# Trajectory
# ---------------------------------------------------------------------------


def _ordered_subsequence(expected: tuple[str, ...], actual: list[str]) -> bool:
    """True if every expected tool appears in ``actual`` in the expected order."""
    it = iter(actual)
    return all(any(tool == candidate for candidate in it) for tool in expected)


def _longest_ordered_subseq_len(expected: tuple[str, ...], actual: list[str]) -> int:
    """Length of the longest prefix of ``expected`` that is an ordered subsequence of ``actual``.

    More precisely: the count of items in ``expected`` (taken in order) that can
    be matched greedily from left to right in ``actual``.  This is the natural
    partial-credit measure for order-sensitive modes: a fully-present but
    misordered sequence yields a count < len(expected) because the greedy scan
    fails once order is broken.
    """
    it = iter(actual)
    count = 0
    for tool in expected:
        if any(candidate == tool for candidate in it):
            count += 1
        else:
            break
    return count


def score_trajectory(actual_tool_names: list[str], scenario: Scenario) -> float:
    """Score the called-tool sequence against the scenario's expected trajectory.

    EXACT     -> identical ordered sequence.  10.0 iff actual == expected exactly.
    IN_ORDER  -> expected is an ordered subsequence of actual.  10.0 iff so.
    ANY_ORDER -> set(expected) <= set(actual).  10.0 iff so.

    Full match -> 10.0.

    Partial scores (non-match):
    - ANY_ORDER: membership fraction x 10 (present tools / expected tools).
    - EXACT / IN_ORDER: (longest in-order match length / len(expected)) x 10.
      This guarantees a fully-present-but-misordered sequence scores < 10.0
      because the greedy ordered-match scan stops before exhausting expected.
    """
    from tests.eval.scenarios import TrajectoryMode

    expected = scenario.expected_tools
    if not expected:
        return _MAX_SCORE

    mode = scenario.trajectory_mode

    if mode is TrajectoryMode.EXACT:
        if tuple(actual_tool_names) == expected:
            return _MAX_SCORE
        length = _longest_ordered_subseq_len(expected, actual_tool_names)
        return _MAX_SCORE * length / len(expected)

    if mode is TrajectoryMode.IN_ORDER:
        if _ordered_subsequence(expected, actual_tool_names):
            return _MAX_SCORE
        length = _longest_ordered_subseq_len(expected, actual_tool_names)
        return _MAX_SCORE * length / len(expected)

    # ANY_ORDER: set membership fraction (original behaviour preserved).
    if set(expected) <= set(actual_tool_names):
        return _MAX_SCORE
    actual_set = set(actual_tool_names)
    present = sum(1 for tool in expected if tool in actual_set)
    return _MAX_SCORE * present / len(expected)


# ---------------------------------------------------------------------------
# Token cost
# ---------------------------------------------------------------------------


def _payload_bytes(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, default=str))


def score_token_cost(
    payloads: list[dict[str, Any]],
    budgets: list[int] | None,
) -> tuple[float, list[int]]:
    """Score per-call payload size against per-call byte budgets.

    Returns ``(score, measured_bytes_by_call_index)``. On the first baseline run
    there is no budget (``budgets is None``): the measured bytes become the budget
    and the score is a clean 10.0. On later runs the score is 10.0 when every call
    is within its recorded budget; if any call exceeds its budget the score scales
    down by the mean per-call (budget / measured) ratio, capped at 1.0 per call.
    """
    measured = [_payload_bytes(p) for p in payloads]
    if budgets is None:
        return _MAX_SCORE, measured
    if not measured:
        return _MAX_SCORE, measured

    ratios: list[float] = []
    for idx, used in enumerate(measured):
        budget = budgets[idx] if idx < len(budgets) else used
        if budget <= 0:
            ratios.append(1.0 if used <= 0 else 0.0)
        else:
            ratios.append(min(1.0, budget / used) if used > 0 else 1.0)
    return _MAX_SCORE * (sum(ratios) / len(ratios)), measured


# ---------------------------------------------------------------------------
# Envelope conformance
# ---------------------------------------------------------------------------


def _non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


# Tools that take no arguments are directly callable with {}; every other tool
# must carry concrete arguments for the next step to be executable.
_NO_ARG_TOOLS = frozenset({"get_server_capabilities", "get_gnomad_diagnostics", "get_clinvar_meta"})


def _valid_next_commands(next_commands: Any) -> bool:
    if not isinstance(next_commands, list) or not next_commands:
        return False
    for cmd in next_commands:
        if not isinstance(cmd, dict):
            return False
        tool = cmd.get("tool")
        if not _non_empty_str(tool):
            return False
        args = cmd.get("arguments")
        if not isinstance(args, dict):
            return False
        if not args and tool not in _NO_ARG_TOOLS:
            return False
    return True


def score_envelope_conformance(payload: dict[str, Any], tool: str, scenario: Scenario) -> float:
    """Return the fraction of applicable envelope checks passed, x 10.

    Checks (each applicable check equally weighted):
      (a) _meta.unsafe_for_clinical_use is True
      (b) _meta.gnomad_release present / non-empty
      (c) if tool in dataset_scoped_tools: _meta.dataset and _meta.reference_genome present
      (d) _meta.next_commands is a non-empty list of dicts each with a non-empty
          tool and concrete arguments (no-arg discovery tools may have {})
      (e) if tool in headline_tools: top-level headline present and non-empty

    This does NOT hard-assert -- Phase 3 raises envelope conformance to 100%.
    """
    meta = payload.get("_meta")
    meta = meta if isinstance(meta, dict) else {}

    checks: list[bool] = []
    # (a)
    checks.append(meta.get("unsafe_for_clinical_use") is True)
    # (b)
    checks.append(_non_empty_str(meta.get("gnomad_release")))
    # (c) only when the tool is dataset-scoped
    if tool in scenario.dataset_scoped_tools:
        checks.append(_non_empty_str(meta.get("dataset")))
        checks.append(_non_empty_str(meta.get("reference_genome")))
    # (d)
    checks.append(_valid_next_commands(meta.get("next_commands")))
    # (e) only when the tool must carry a headline
    if tool in scenario.headline_tools:
        checks.append(_non_empty_str(payload.get("headline")))

    if not checks:
        return _MAX_SCORE
    return _MAX_SCORE * sum(1 for c in checks if c) / len(checks)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


@dataclass
class Scorecard:
    """Aggregated, per-dimension eval result on a 0..10 scale."""

    trajectory: float
    token_cost: float
    envelope_conformance: float
    total: float
    # Raw measured payload bytes per scenario: {scenario_name: [bytes_per_call]}.
    measured_bytes: dict[str, list[int]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trajectory": round(self.trajectory, 6),
            "token_cost": round(self.token_cost, 6),
            "envelope_conformance": round(self.envelope_conformance, 6),
            "total": round(self.total, 6),
            "measured_bytes": self.measured_bytes,
        }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else _MAX_SCORE


def aggregate(per_scenario_dimension_scores: dict[str, dict[str, Any]]) -> Scorecard:
    """Mean the per-scenario dimension scores into a Scorecard.

    ``per_scenario_dimension_scores`` maps each scenario name to a dict with
    ``trajectory``, ``token_cost``, ``envelope_conformance`` floats and a
    ``measured_bytes`` list. The per-dimension means are themselves averaged
    (equal weighting) into ``total``.
    """
    trajectory = _mean([s["trajectory"] for s in per_scenario_dimension_scores.values()])
    token_cost = _mean([s["token_cost"] for s in per_scenario_dimension_scores.values()])
    envelope = _mean([s["envelope_conformance"] for s in per_scenario_dimension_scores.values()])
    total = (trajectory + token_cost + envelope) / 3.0
    measured_bytes = {
        name: list(scores.get("measured_bytes", []))
        for name, scores in per_scenario_dimension_scores.items()
    }
    return Scorecard(
        trajectory=trajectory,
        token_cost=token_cost,
        envelope_conformance=envelope,
        total=total,
        measured_bytes=measured_bytes,
    )
