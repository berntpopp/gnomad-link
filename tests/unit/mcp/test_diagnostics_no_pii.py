"""Cross-session PII disclosure regression test (finding M4, decision D2).

``get_diagnostics`` returns two process-global error rings. Before this fix the
rings stored raw exception text (``message`` / ``raw_message``) and raw upstream
schema-drift text, so one caller's variant coordinates / rejected input could
leak to a different caller. Every ring record must reduce to non-PII fields only
(``tool_name``, ``error_code``, ``exc_type`` for errors; ``tool_name`` +
``error_field`` for drift) and the raw text must appear NOWHERE in the
get_diagnostics output.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

# A caller-supplied token that stands in for PII (a variant coordinate or a
# rejected raw input). It must not survive into another caller's diagnostics.
SENTINEL = "SENTINEL-PII-7f3a"


@pytest.mark.asyncio
async def test_get_diagnostics_never_leaks_raw_error_or_drift_text() -> None:
    from gnomad_link.api import DataNotFoundError
    from gnomad_link.mcp.errors import (
        McpErrorContext,
        clear_recent_errors,
        clear_recent_schema_drift,
        run_mcp_tool,
    )
    from gnomad_link.mcp.facade import create_gnomad_mcp
    from gnomad_link.mcp.output_validation import actionable_output_validation_error

    clear_recent_errors()
    clear_recent_schema_drift()

    # (a) Drive a real error whose exception message embeds the sentinel into the
    # recent-errors ring (this is exactly how DataNotFoundError embeds a caller's
    # processed variables, see api/base_client.py).
    async def failing_call() -> dict[str, object]:
        raise DataNotFoundError(
            "No data found for get_variant with parameters: "
            f"{{'variant_id': '1-55516888-G-GA', 'caller_note': '{SENTINEL}'}}"
        )

    await run_mcp_tool(
        "get_variant_frequencies",
        failing_call,
        context=McpErrorContext(tool_name="get_variant_frequencies", variant_id="1-55516888-G-GA"),
    )

    # (b) Drive a schema-drift event whose raw SDK text embeds the sentinel into
    # both the recent-errors ring and the schema-drift ring.
    actionable_output_validation_error(
        tool_name="get_variant_frequencies",
        arguments={"variant_id": SENTINEL},
        message=(
            "Output validation error: 'exome' is a required property; "
            f"upstream payload was {{'variant_id': '{SENTINEL}'}}"
        ),
    )

    service = AsyncMock()
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool("get_diagnostics", {})
    payload = result.structured_content or {}

    # Sanity: the rings actually captured the events we drove.
    assert payload["recent_error_count"] >= 1
    assert payload["recent_schema_drift_count"] >= 1

    # The sentinel must appear NOWHERE in the full diagnostics output -- across
    # recent_errors AND recent_schema_drift.
    blob = json.dumps(payload)
    assert SENTINEL not in blob, (
        "Raw caller text leaked through get_diagnostics rings: "
        f"{payload.get('recent_errors', [])} / "
        f"{payload.get('recent_schema_drift', [])}"
    )
