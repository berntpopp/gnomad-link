"""Tests for output-schema-drift observability (Hot-Fix H4).

The general recent_errors ring records every error code; output-schema drift
is rare but symptomatic (upstream payload shape no longer matches our declared
output_schema). A separate bounded ring lets an LLM hitting
``output_validation_failed`` call ``get_gnomad_diagnostics`` and self-diagnose
without scraping free text or escalating to a human.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


def test_record_schema_drift_appends_to_ring() -> None:
    from gnomad_link.mcp.errors import (
        clear_recent_schema_drift,
        get_recent_schema_drift,
        record_schema_drift,
    )

    clear_recent_schema_drift()
    record_schema_drift(tool_name="t1", error_field="x", message="msg")
    record_schema_drift(tool_name="t2", error_field=None, message="msg2")
    items = get_recent_schema_drift()
    assert len(items) == 2
    assert items[0]["tool_name"] == "t1"
    assert items[0]["error_field"] == "x"
    assert items[0]["message"] == "msg"
    assert items[1]["tool_name"] == "t2"
    assert items[1]["error_field"] is None
    assert items[1]["message"] == "msg2"


def test_record_schema_drift_ring_caps_at_limit() -> None:
    from gnomad_link.mcp.errors import (
        RECENT_SCHEMA_DRIFT_LIMIT,
        clear_recent_schema_drift,
        get_recent_schema_drift,
        record_schema_drift,
    )

    clear_recent_schema_drift()
    for i in range(RECENT_SCHEMA_DRIFT_LIMIT * 2):
        record_schema_drift(tool_name=f"t{i}", error_field="x", message="m")
    items = get_recent_schema_drift()
    assert len(items) == RECENT_SCHEMA_DRIFT_LIMIT


def test_record_schema_drift_truncates_long_messages() -> None:
    from gnomad_link.mcp.errors import (
        clear_recent_schema_drift,
        get_recent_schema_drift,
        record_schema_drift,
    )

    clear_recent_schema_drift()
    long_message = "x" * 5000
    record_schema_drift(tool_name="t1", error_field="x", message=long_message)
    items = get_recent_schema_drift()
    assert len(items) == 1
    # The recorder should not surface unbounded upstream text.
    assert len(items[0]["message"]) <= 500


def test_actionable_output_validation_error_records_schema_drift() -> None:
    from gnomad_link.mcp.errors import clear_recent_schema_drift, get_recent_schema_drift
    from gnomad_link.mcp.output_validation import actionable_output_validation_error

    clear_recent_schema_drift()
    payload = actionable_output_validation_error(
        tool_name="get_variant_frequencies",
        arguments={"variant_id": "X"},
        message="Output validation error: 'variant_id' is a required property",
    )

    assert payload["success"] is False
    assert payload["error_code"] == "output_validation_failed"

    items = get_recent_schema_drift()
    assert len(items) == 1
    assert items[0]["tool_name"] == "get_variant_frequencies"
    assert items[0]["error_field"] == "variant_id"
    assert "variant_id" in items[0]["message"]


@pytest.mark.asyncio
async def test_get_gnomad_diagnostics_includes_recent_schema_drift() -> None:
    from gnomad_link.mcp.errors import clear_recent_schema_drift, record_schema_drift
    from gnomad_link.mcp.facade import create_gnomad_mcp

    clear_recent_schema_drift()
    record_schema_drift(
        tool_name="get_variant_frequencies",
        error_field="exome",
        message="drift",
    )

    service = AsyncMock()
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool("get_gnomad_diagnostics", {})
    payload = result.structured_content or {}

    assert "recent_schema_drift" in payload
    assert "recent_schema_drift_count" in payload
    drift = payload["recent_schema_drift"]
    assert isinstance(drift, list)
    assert len(drift) == payload["recent_schema_drift_count"]
    assert len(drift) >= 1
    assert any(item["tool_name"] == "get_variant_frequencies" for item in drift)


@pytest.mark.asyncio
async def test_get_gnomad_diagnostics_recent_schema_drift_is_empty_by_default() -> None:
    from gnomad_link.mcp.errors import clear_recent_schema_drift
    from gnomad_link.mcp.facade import create_gnomad_mcp

    clear_recent_schema_drift()

    service = AsyncMock()
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool("get_gnomad_diagnostics", {})
    payload = result.structured_content or {}

    assert payload["recent_schema_drift"] == []
    assert payload["recent_schema_drift_count"] == 0


def test_record_schema_drift_does_not_count_toward_recent_errors() -> None:
    """Drift records are observability-only; they go to a separate ring."""
    from gnomad_link.mcp.errors import (
        clear_recent_errors,
        clear_recent_schema_drift,
        get_recent_errors,
        record_schema_drift,
    )

    clear_recent_errors()
    clear_recent_schema_drift()
    record_schema_drift(tool_name="t1", error_field="x", message="msg")
    # The general error ring stays empty when only schema drift is recorded.
    assert get_recent_errors() == []
