from __future__ import annotations

import json

import pytest


def test_mcp_tool_error_envelope_contains_required_fields() -> None:
    from gnomad_link.mcp.errors import McpErrorContext, mcp_tool_error

    err = mcp_tool_error(
        ValueError("invalid variant id 'abc'"),
        McpErrorContext(tool_name="get_variant_frequencies", variant_id="abc"),
    )
    payload = json.loads(str(err))

    assert payload["success"] is False
    assert payload["error_code"] == "validation_failed"
    assert payload["retryable"] is False
    assert "abc" not in payload["message"] or payload["message"].startswith("Invalid")
    assert payload["fallback_tool"] in {"get_server_capabilities", None}
    assert "_meta" in payload
    assert payload["_meta"]["unsafe_for_clinical_use"] is True


def test_data_not_found_maps_to_not_found_code() -> None:
    from gnomad_link.api import DataNotFoundError
    from gnomad_link.mcp.errors import McpErrorContext, mcp_tool_error

    err = mcp_tool_error(
        DataNotFoundError("variant 1-99999999-N-N not in gnomad_r4"),
        McpErrorContext(tool_name="get_variant_frequencies", variant_id="1-99999999-N-N"),
    )
    payload = json.loads(str(err))

    assert payload["error_code"] == "not_found"
    assert payload["retryable"] is False
    assert payload["recovery"]


def test_upstream_api_error_is_retryable() -> None:
    from gnomad_link.api import GnomadApiError
    from gnomad_link.mcp.errors import McpErrorContext, mcp_tool_error

    err = mcp_tool_error(
        GnomadApiError("upstream 503"),
        McpErrorContext(tool_name="get_variant_frequencies"),
    )
    payload = json.loads(str(err))

    assert payload["error_code"] == "upstream_unavailable"
    assert payload["retryable"] is True


@pytest.mark.asyncio
async def test_run_mcp_tool_returns_envelope_on_exception() -> None:
    from gnomad_link.mcp.errors import run_mcp_tool

    async def boom() -> None:
        raise RuntimeError("oh no a secret: SECRET")

    result = await run_mcp_tool("test_tool", boom)

    assert result["success"] is False
    assert result["error_code"] == "internal_error"
    assert "SECRET" not in result["message"]


@pytest.mark.asyncio
async def test_run_mcp_tool_passes_through_success_payload() -> None:
    from gnomad_link.mcp.errors import run_mcp_tool

    async def ok() -> dict[str, str]:
        return {"ok": "yes"}

    result = await run_mcp_tool("test_tool", ok)

    assert result == {"ok": "yes"}


def test_recent_error_ring_is_bounded() -> None:
    from gnomad_link.mcp.errors import RECENT_MCP_ERROR_LIMIT, get_recent_errors, record_mcp_error

    for i in range(RECENT_MCP_ERROR_LIMIT + 10):
        record_mcp_error(
            tool_name="get_variant_frequencies",
            error_code="internal_error",
            message=f"err {i}",
            raw_message=f"err {i}",
        )

    history = get_recent_errors()
    assert len(history) == RECENT_MCP_ERROR_LIMIT
