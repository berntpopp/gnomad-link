"""Tests for output-schema-drift observability (Hot-Fix H4).

The general recent_errors ring records every error code; output-schema drift
is rare but symptomatic (upstream payload shape no longer matches our declared
output_schema). A separate bounded ring lets an LLM hitting
``output_validation_failed`` call ``get_diagnostics`` and self-diagnose
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
    record_schema_drift(tool_name="t1", error_field="x")
    record_schema_drift(tool_name="t2", error_field=None)
    items = get_recent_schema_drift()
    assert len(items) == 2
    assert items[0]["tool_name"] == "t1"
    assert items[0]["error_field"] == "x"
    assert items[1]["tool_name"] == "t2"
    assert items[1]["error_field"] is None
    # The drift ring carries only non-PII fields (finding M4): no raw message.
    assert set(items[0]) == {"tool_name", "error_field"}
    assert "message" not in items[0]


def test_record_schema_drift_ring_caps_at_limit() -> None:
    from gnomad_link.mcp.errors import (
        RECENT_SCHEMA_DRIFT_LIMIT,
        clear_recent_schema_drift,
        get_recent_schema_drift,
        record_schema_drift,
    )

    clear_recent_schema_drift()
    for i in range(RECENT_SCHEMA_DRIFT_LIMIT * 2):
        record_schema_drift(tool_name=f"t{i}", error_field="x")
    items = get_recent_schema_drift()
    assert len(items) == RECENT_SCHEMA_DRIFT_LIMIT


def test_record_schema_drift_never_stores_raw_message() -> None:
    """The drift ring must not retain raw upstream text (finding M4)."""
    from gnomad_link.mcp.errors import (
        clear_recent_schema_drift,
        get_recent_schema_drift,
        record_schema_drift,
    )

    clear_recent_schema_drift()
    record_schema_drift(tool_name="t1", error_field="x")
    items = get_recent_schema_drift()
    assert len(items) == 1
    # No raw-text key of any kind may cross into the caller-facing ring.
    assert set(items[0]) == {"tool_name", "error_field"}
    assert "message" not in items[0]


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
    # The envelope emits the closed-enum wire code; the schema-drift ring still
    # records the specific `output_validation_failed` classification.
    assert payload["error_code"] == "internal"

    items = get_recent_schema_drift()
    assert len(items) == 1
    assert items[0]["tool_name"] == "get_variant_frequencies"
    assert items[0]["error_field"] == "variant_id"
    # The parsed field name is retained; the raw SDK message is not (finding M4).
    assert "message" not in items[0]


@pytest.mark.asyncio
async def test_get_diagnostics_includes_recent_schema_drift() -> None:
    from gnomad_link.mcp.errors import clear_recent_schema_drift, record_schema_drift
    from gnomad_link.mcp.facade import create_gnomad_mcp

    clear_recent_schema_drift()
    record_schema_drift(
        tool_name="get_variant_frequencies",
        error_field="exome",
    )

    service = AsyncMock()
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool("get_diagnostics", {})
    payload = result.structured_content or {}

    assert "recent_schema_drift" in payload
    assert "recent_schema_drift_count" in payload
    drift = payload["recent_schema_drift"]
    assert isinstance(drift, list)
    assert len(drift) == payload["recent_schema_drift_count"]
    assert len(drift) >= 1
    assert any(item["tool_name"] == "get_variant_frequencies" for item in drift)


@pytest.mark.asyncio
async def test_get_diagnostics_recent_schema_drift_is_empty_by_default() -> None:
    from gnomad_link.mcp.errors import clear_recent_schema_drift
    from gnomad_link.mcp.facade import create_gnomad_mcp

    clear_recent_schema_drift()

    service = AsyncMock()
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool("get_diagnostics", {})
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
    record_schema_drift(tool_name="t1", error_field="x")
    # The general error ring stays empty when only schema drift is recorded.
    assert get_recent_errors() == []
