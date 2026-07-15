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


def test_not_found_on_sv_tool_falls_back_to_a_callable_tool_not_resolver() -> None:
    # SV ids are NOT resolvable by resolve_variant_id (SNV-only). search_structural_variants
    # now requires a `target` we do not have from an SV-id lookup, so a bare call would be
    # uncallable; the callable fallback is capabilities (the recovery prose names SV search).
    payload = _payload(
        DataNotFoundError("DEL_chr1_1 not found"),
        McpErrorContext(tool_name="get_structural_variant", variant_id="DEL_chr1_1"),
    )
    assert payload["error_code"] == "not_found"
    assert payload["fallback_tool"] == "get_server_capabilities"
    assert payload["fallback_tool"] != "resolve_variant_id"
    # The advertised next_command must be directly callable (no required args missing).
    assert payload["fallback_args"] in (None, {})


def test_sv_search_not_found_steers_to_gene_search() -> None:
    payload = _payload(
        DataNotFoundError("no SVs for gene"),
        McpErrorContext(tool_name="search_structural_variants", gene_symbol="NOTAGENE"),
    )
    assert payload["fallback_tool"] == "search_genes"
    assert payload["fallback_args"] == {"query": "NOTAGENE"}


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


def test_not_found_on_mito_tool_does_not_route_to_resolver() -> None:
    # M-POS-REF-ALT ids are not resolvable by resolve_variant_id (SNV/indel only).
    payload = _payload(
        DataNotFoundError("M-3243-A-G not found"),
        McpErrorContext(tool_name="get_mitochondrial_variant", variant_id="M-3243-A-G"),
    )
    assert payload["error_code"] == "not_found"
    assert payload["fallback_tool"] == "get_server_capabilities"
    assert payload["fallback_tool"] != "resolve_variant_id"
    # Mito-aware recovery prose: name the mito datasets, drop the SNV resolver clause.
    assert "resolve_variant_id" not in payload["recovery"]
    assert "gnomad_r4" in payload["recovery"]


def test_not_found_on_sv_tool_has_sv_dataset_recovery_prose() -> None:
    payload = _payload(
        DataNotFoundError("BND_chr12_x not found"),
        McpErrorContext(tool_name="get_structural_variant", variant_id="BND_chr12_x"),
    )
    assert payload["error_code"] == "not_found"
    assert "gnomad_sv_r4" in payload["recovery"]
    assert "r3/r2_1" not in payload["recovery"]


def test_error_next_commands_prepends_classified_fallback() -> None:
    from gnomad_link.mcp.errors import BuildMismatchError

    payload = _payload(
        BuildMismatchError(
            variant_id="1-249100000-A-T", inferred_build="GRCh37", dataset="gnomad_r4"
        ),
        McpErrorContext(tool_name="get_variant_frequencies", variant_id="1-249100000-A-T"),
    )
    cmds = payload["_meta"]["next_commands"]
    # The task-advancing resolver leads; diagnostics stays as the secondary entry.
    assert cmds[0]["tool"] == "compute_variant_liftover"
    assert cmds[0]["arguments"]["source_genome"] == "GRCh37"
    assert cmds[-1]["tool"] == "get_diagnostics"


def test_retryable_error_next_commands_is_diagnostics_only() -> None:
    payload = _payload(
        RateLimitedError("Rate limited by upstream API (HTTP 429)"),
        McpErrorContext(tool_name="get_variant_frequencies", variant_id="1-1-A-T"),
    )
    cmds = payload["_meta"]["next_commands"]
    # Retry, not switch: fallback_tool is already diagnostics, so no duplicate prepend.
    assert [c["tool"] for c in cmds] == ["get_diagnostics"]


def test_error_meta_echoes_dataset_and_build() -> None:
    payload = _payload(
        DataNotFoundError("variant not found"),
        McpErrorContext(
            tool_name="get_variant_frequencies", variant_id="1-1-A-T", dataset="gnomad_r4"
        ),
    )
    assert payload["_meta"]["dataset"] == "gnomad_r4"
    assert payload["_meta"]["reference_genome"] == "GRCh38"
