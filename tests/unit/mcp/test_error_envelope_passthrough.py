"""H1 regression: structured error envelopes must survive MCP output-schema validation.

Before this fix, the MCP SDK validated every tool response against the declared
output_schema, and when an error envelope (success=False, error_code=...) did not
match the success-shaped schema's `required` fields, the SDK discarded the payload
and replaced it with a generic "Output validation error" message. Our handler then
wrapped that as `output_validation_failed`, erasing the original error_code.

These tests route through the SDK lowlevel CallToolRequest handler (not just the
in-process FastMCP `call_tool` wrapper) so they exercise the same validation path
hit by real HTTP/stdio transports.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

import mcp.types

# ---------------------------------------------------------------------------
# Helper unit tests for relax_output_schema
# ---------------------------------------------------------------------------


def test_relax_output_schema_strips_required() -> None:
    from gnomad_link.mcp.schema_relax import relax_output_schema

    schema = {
        "type": "object",
        "required": ["a", "b"],
        "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
        "additionalProperties": False,
    }
    relaxed = relax_output_schema(schema)

    assert "required" not in relaxed
    assert relaxed["additionalProperties"] is True
    assert relaxed["properties"]["a"] == {"type": "string"}


def test_relax_output_schema_recurses_into_nested_structures() -> None:
    from gnomad_link.mcp.schema_relax import relax_output_schema

    schema: dict[str, Any] = {
        "type": "object",
        "required": ["outer"],
        "properties": {
            "outer": {
                "type": "object",
                "required": ["inner"],
                "properties": {"inner": {"type": "string"}},
                "additionalProperties": False,
            },
            "items_list": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["x"],
                    "properties": {"x": {"type": "integer"}},
                },
            },
        },
        "$defs": {
            "Nested": {
                "type": "object",
                "required": ["y"],
                "properties": {"y": {"type": "number"}},
            }
        },
        "oneOf": [
            {"type": "object", "required": ["a"], "properties": {"a": {"type": "string"}}},
            {"type": "object", "required": ["b"], "properties": {"b": {"type": "string"}}},
        ],
    }
    relaxed = relax_output_schema(schema)

    assert "required" not in relaxed
    assert "required" not in relaxed["properties"]["outer"]
    assert relaxed["properties"]["outer"]["additionalProperties"] is True
    assert "required" not in relaxed["properties"]["items_list"]["items"]
    assert "required" not in relaxed["$defs"]["Nested"]
    for branch in relaxed["oneOf"]:
        assert "required" not in branch


# ---------------------------------------------------------------------------
# Stub service used by error-envelope passthrough tests
# ---------------------------------------------------------------------------


class _ConfigurableStubService:
    """Stub FrequencyService whose `get_variant_frequencies` is configured per-test."""

    def __init__(self, *, freq_handler: Any) -> None:
        self._freq_handler = freq_handler

    async def get_variant_frequencies(self, variant_id: str, dataset: str) -> object:
        return await self._freq_handler(variant_id, dataset)


def _is_envelope(payload: dict[str, Any], expected_code: str) -> bool:
    return (
        isinstance(payload, dict)
        and payload.get("success") is False
        and payload.get("error_code") == expected_code
    )


async def _invoke(mcp_instance: Any, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Invoke a tool through the SDK lowlevel CallToolRequest handler.

    This is the same code path that real HTTP/stdio transports use, so it
    exercises the SDK's output-schema validation. Returns the structured
    content dict from the resulting CallToolResult; if no structuredContent
    is present, decodes the first text content as JSON.
    """
    handler = mcp_instance._mcp_server.request_handlers[mcp.types.CallToolRequest]
    request = mcp.types.CallToolRequest(
        method="tools/call",
        params=mcp.types.CallToolRequestParams(name=tool_name, arguments=arguments),
    )
    result = await handler(request)
    call_result = result.root if hasattr(result, "root") else result
    assert isinstance(call_result, mcp.types.CallToolResult)
    if call_result.structuredContent is not None:
        return dict(call_result.structuredContent)
    if call_result.content:
        first = call_result.content[0]
        text = getattr(first, "text", None)
        if isinstance(text, str):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"_raw_text": text}
    return {}


# ---------------------------------------------------------------------------
# Error envelope passthrough tests (via SDK lowlevel handler)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_not_found_envelope_survives_output_schema() -> None:
    """DataNotFoundError must become error_code='not_found', not output_validation_failed."""

    from gnomad_link.api import DataNotFoundError
    from gnomad_link.mcp.facade import create_gnomad_mcp

    async def boom(variant_id: str, dataset: str) -> object:
        raise DataNotFoundError(f"variant {variant_id} not present in {dataset}")

    service = _ConfigurableStubService(freq_handler=boom)
    mcp_instance = create_gnomad_mcp(service_factory=lambda: service)

    payload = await _invoke(
        mcp_instance,
        "get_variant_frequencies",
        {"variant_id": "1-55051215-G-GA", "dataset": "gnomad_r4"},
    )

    assert _is_envelope(payload, "not_found"), payload
    assert payload.get("error_code") != "output_validation_failed"


@pytest.mark.asyncio
async def test_build_mismatch_envelope_survives_output_schema() -> None:
    """A GRCh37-only coordinate against gnomad_r4 must surface error_code='build_mismatch'."""

    from gnomad_link.mcp.facade import create_gnomad_mcp

    async def never_called(variant_id: str, dataset: str) -> object:
        raise AssertionError("upstream must not be invoked on build_mismatch")

    service = _ConfigurableStubService(freq_handler=never_called)
    mcp_instance = create_gnomad_mcp(service_factory=lambda: service)

    payload = await _invoke(
        mcp_instance,
        "get_variant_frequencies",
        {"variant_id": "1-249100000-A-T", "dataset": "gnomad_r4"},
    )

    assert _is_envelope(payload, "build_mismatch"), payload
    assert payload.get("error_code") != "output_validation_failed"
    assert payload.get("fallback_tool") == "liftover_variant"


@pytest.mark.asyncio
async def test_upstream_error_envelope_survives_output_schema() -> None:
    """GnomadApiError must surface as upstream_unavailable, retryable=True."""

    from gnomad_link.api import GnomadApiError
    from gnomad_link.mcp.facade import create_gnomad_mcp

    async def boom(variant_id: str, dataset: str) -> object:
        raise GnomadApiError("upstream timeout")

    service = _ConfigurableStubService(freq_handler=boom)
    mcp_instance = create_gnomad_mcp(service_factory=lambda: service)

    payload = await _invoke(
        mcp_instance,
        "get_variant_frequencies",
        {"variant_id": "1-55051215-G-GA", "dataset": "gnomad_r4"},
    )

    assert _is_envelope(payload, "upstream_unavailable"), payload
    assert payload.get("retryable") is True
    assert payload.get("error_code") != "output_validation_failed"


@pytest.mark.asyncio
async def test_validation_error_envelope_survives_output_schema() -> None:
    """Argument validation failure must surface as validation_failed, with field_errors."""

    from gnomad_link.mcp.facade import create_gnomad_mcp

    async def never_called(variant_id: str, dataset: str) -> object:
        raise AssertionError("upstream must not be invoked on validation failure")

    service = _ConfigurableStubService(freq_handler=never_called)
    mcp_instance = create_gnomad_mcp(service_factory=lambda: service)

    payload = await _invoke(
        mcp_instance,
        "get_variant_frequencies",
        {"variant_id": "not-a-variant", "dataset": "gnomad_r4"},
    )

    assert _is_envelope(payload, "validation_failed"), payload
    assert payload.get("error_code") != "output_validation_failed"
    assert payload.get("field_errors")


@pytest.mark.asyncio
async def test_internal_error_envelope_survives_output_schema() -> None:
    """An unexpected RuntimeError must surface as error_code='internal_error'."""

    from gnomad_link.mcp.facade import create_gnomad_mcp

    async def boom(variant_id: str, dataset: str) -> object:
        raise RuntimeError("kaboom")

    service = _ConfigurableStubService(freq_handler=boom)
    mcp_instance = create_gnomad_mcp(service_factory=lambda: service)

    payload = await _invoke(
        mcp_instance,
        "get_variant_frequencies",
        {"variant_id": "1-55051215-G-GA", "dataset": "gnomad_r4"},
    )

    assert _is_envelope(payload, "internal_error"), payload
    assert payload.get("error_code") != "output_validation_failed"


@pytest.mark.asyncio
async def test_success_response_still_passes_output_schema() -> None:
    """A normal success payload must come through with the expected fields."""

    from gnomad_link.mcp.facade import create_gnomad_mcp
    from gnomad_link.models import VariantFrequencyResponse

    async def ok(variant_id: str, dataset: str) -> object:
        return VariantFrequencyResponse(
            variant_id=variant_id, dataset=dataset, exome=None, genome=None
        )

    service = _ConfigurableStubService(freq_handler=ok)
    mcp_instance = create_gnomad_mcp(service_factory=lambda: service)

    payload = await _invoke(
        mcp_instance,
        "get_variant_frequencies",
        {"variant_id": "1-55051215-G-GA", "dataset": "gnomad_r4"},
    )

    assert payload.get("success") is not False, payload
    assert payload.get("error_code") is None
    assert payload.get("variant_id") == "1-55051215-G-GA"
    assert payload.get("dataset") == "gnomad_r4"
