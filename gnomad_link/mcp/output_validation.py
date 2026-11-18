"""Output-schema validation error interceptor for gnomAD Link MCP tools.

Ported from pubtator_link/mcp/output_validation.py. When FastMCP fires an
output-schema validation error, this handler wraps it in the standard
gnomad-link error envelope so LLM callers see a structured actionable response
instead of a raw SDK error string.
"""

from __future__ import annotations

import json
import re
from typing import Any

import mcp.types

from gnomad_link.mcp.errors import (
    _FALLBACK_TOOL,
    _provenance_meta,
    record_mcp_error,
    record_schema_drift,
)

OUTPUT_VALIDATION_PREFIX = "Output validation error:"
_REQUIRED_PROPERTY_RE = re.compile(r"'(?P<field>[^']+)' is a required property")


def actionable_output_validation_error(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    message: str,
) -> dict[str, Any]:
    """Return and record an actionable MCP output-schema validation failure."""
    error_field = _output_validation_field(message)
    suggested_action = (
        f"Tool response failed output schema validation on field '{error_field}'. "
        f"This usually indicates upstream schema drift; call {_FALLBACK_TOOL} for context."
    )
    payload: dict[str, Any] = {
        "success": False,
        "error_code": "internal",
        "message": "The tool response did not match its declared MCP output schema.",
        "error_field": error_field,
        "suggested_action": suggested_action,
        "_meta": {
            "next_commands": [
                {"tool": _FALLBACK_TOOL, "arguments": {}},
            ],
            **_provenance_meta(),
        },
    }
    # Record only non-PII fields into the caller-facing rings (finding M4): the
    # raw SDK `message` can embed the upstream payload / caller input, and
    # get_diagnostics returns these rings to any caller. `exc_type` is a constant
    # for this boundary (the SDK raises no distinct exception class here).
    record_mcp_error(
        tool_name=tool_name,
        error_code="output_validation_failed",
        exc_type="OutputSchemaValidationError",
    )
    # Also surface the event on the dedicated schema-drift ring so an LLM
    # hitting the output_validation_failed envelope can call
    # get_diagnostics and inspect which fields/tools are drifting. Only the
    # parsed `error_field` (a property name from our own output schema) crosses
    # the boundary -- never the raw message.
    record_schema_drift(
        tool_name=tool_name,
        error_field=error_field,
    )
    return payload


def install_output_validation_error_handler(mcp_server: Any) -> None:
    """Wrap the MCP call-tool handler so SDK output validation errors are observable."""
    lowlevel = mcp_server._mcp_server
    entry = lowlevel.get_request_handler("tools/call")
    if entry is None:
        return

    async def wrapped(ctx: Any, params: Any, *, _orig: Any = entry.handler) -> Any:
        call_result = await _orig(ctx, params)
        if not isinstance(call_result, mcp.types.CallToolResult):
            return call_result
        if not call_result.is_error or not call_result.content:
            return call_result
        first_content = call_result.content[0]
        message = getattr(first_content, "text", "")
        if not isinstance(message, str) or not message.startswith(OUTPUT_VALIDATION_PREFIX):
            return call_result
        payload = actionable_output_validation_error(
            tool_name=params.name,
            arguments=params.arguments or {},
            message=message,
        )
        return mcp.types.CallToolResult(
            content=[
                mcp.types.TextContent(
                    type="text",
                    text=json.dumps(payload, separators=(",", ":"), sort_keys=True),
                )
            ],
            # Carry the structured envelope too: an isError result that nulls
            # structuredContent loses the machine-readable error frame a client
            # branches on (same contract as the ToolResult chokepoint).
            structured_content=payload,
            is_error=True,
        )

    lowlevel.add_request_handler("tools/call", entry.params_type, wrapped)


def _output_validation_field(message: str) -> str | None:
    match = _REQUIRED_PROPERTY_RE.search(message)
    if match is not None:
        return match.group("field")
    return None
