"""M-2/L-5: error taxonomy — deterministic input faults are non-retryable, 429 is
retryable, and not_found/invalid_input fallbacks are context-aware.

The old behavior collapsed every non-"not found" upstream GraphQL error into
upstream_unavailable/retryable=true, so a gene symbol passed to a variant tool
("Unrecognized query.") told the LLM to retry forever; and not_found always
suggested search_genes regardless of the calling tool.
"""

from __future__ import annotations

import json

from gnomad_link.api import (
    DataNotFoundError,
    GnomadApiError,
    RateLimitedError,
    UpstreamInputError,
)
from gnomad_link.mcp.errors import McpErrorContext, mcp_tool_error


def _payload(exc, ctx):
    return json.loads(str(mcp_tool_error(exc, ctx)))


def test_upstream_input_error_is_invalid_input_non_retryable() -> None:
    payload = _payload(
        UpstreamInputError("Unrecognized query. Search by variant ID, rsID, or ClinVar ID."),
        McpErrorContext(tool_name="resolve_variant_id"),
    )
    assert payload["error_code"] == "invalid_input"
    assert payload["retryable"] is False
    assert payload["recovery_action"] == "reformulate_input"
    # The recovery must not tell the model to blindly retry with backoff.
    assert "backoff" not in payload["recovery"].lower()
    # The upstream's actionable hint should survive (it teaches the model).
    assert "variant id" in payload["message"].lower()


def test_rate_limited_is_retryable() -> None:
    payload = _payload(
        RateLimitedError("Rate limited by upstream API (HTTP 429)"),
        McpErrorContext(tool_name="get_variant_frequencies", variant_id="1-55051215-G-GA"),
    )
    assert payload["error_code"] == "rate_limited"
    assert payload["retryable"] is True
    assert payload["recovery_action"] == "retry_backoff"


def test_not_found_on_variant_tool_falls_back_to_resolver() -> None:
    payload = _payload(
        DataNotFoundError("variant 1-99999999-N-N not in gnomad_r4"),
        McpErrorContext(tool_name="get_variant_frequencies", variant_id="1-99999999-G-A"),
    )
    assert payload["error_code"] == "not_found"
    assert payload["retryable"] is False
    assert payload["fallback_tool"] == "resolve_variant_id"
    assert payload["fallback_args"] == {"query": "1-99999999-G-A"}
    assert payload["recovery_action"] == "switch_tool"


def test_not_found_on_gene_tool_falls_back_to_search_genes() -> None:
    payload = _payload(
        DataNotFoundError("gene not found"),
        McpErrorContext(tool_name="get_gene_details", gene_symbol="NOTAGENE"),
    )
    assert payload["fallback_tool"] == "search_genes"
    assert payload["fallback_args"] == {"query": "NOTAGENE"}


def test_invalid_input_on_variant_tool_points_to_resolver() -> None:
    payload = _payload(
        UpstreamInputError("Unrecognized query."),
        McpErrorContext(tool_name="get_variant_frequencies", variant_id="BRCA2"),
    )
    assert payload["error_code"] == "invalid_input"
    assert payload["fallback_tool"] == "resolve_variant_id"


def test_invalid_input_on_resolver_points_to_search_genes() -> None:
    # resolve_variant_id given a gene symbol must steer to gene search, not itself.
    payload = _payload(
        UpstreamInputError("Unrecognized query. Search by variant ID, rsID, or ClinVar ID."),
        McpErrorContext(tool_name="resolve_variant_id"),
    )
    assert payload["error_code"] == "invalid_input"
    assert payload["fallback_tool"] == "search_genes"
    assert payload["recovery_action"] == "reformulate_input"


def test_genuine_upstream_fault_stays_retryable() -> None:
    payload = _payload(
        GnomadApiError("GraphQL error: internal server failure"),
        McpErrorContext(tool_name="get_variant_frequencies"),
    )
    assert payload["error_code"] == "upstream_unavailable"
    assert payload["retryable"] is True
    assert payload["recovery_action"] == "retry_backoff"
