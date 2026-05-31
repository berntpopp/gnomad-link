"""Optional agentic/live eval (harness 2b). Opt-in: manual `make eval-live` only.

A full agentic eval would drive a real LLM over the eval scenarios against the
LIVE gnomAD API and score final-answer quality (LLM-as-judge) plus live
trajectory. This scaffold is skipped unless an agentic eval is explicitly
configured, so it never runs in default CI and never fails without credentials.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    not os.getenv("GNOMAD_EVAL_AGENTIC"),
    reason="Agentic/live eval is opt-in; set GNOMAD_EVAL_AGENTIC=1 and provide model credentials.",
)
def test_agentic_eval_scaffold() -> None:
    pytest.skip("Agentic eval loop not yet implemented; scaffold only (harness 2b).")
