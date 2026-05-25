"""Structured MCP error envelopes for gnomAD Link tools.

Patterned after pubtator_link/mcp/errors.py. The envelope shape is what LLMs
branch on; codes are deterministic per exception class so prompts can recover
without scraping free text.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from gnomad_link.api import DataNotFoundError, GnomadApiError

logger = logging.getLogger(__name__)

RECENT_MCP_ERROR_LIMIT = 50
_RECENT_ERRORS: deque[dict[str, Any]] = deque(maxlen=RECENT_MCP_ERROR_LIMIT)

_RESEARCH_USE_META = {"unsafe_for_clinical_use": True}


@dataclass
class McpErrorContext:
    """Per-call context passed to the error builder so envelopes can suggest fallbacks."""

    tool_name: str
    variant_id: str | None = None
    gene_id: str | None = None
    gene_symbol: str | None = None
    region: str | None = None
    dataset: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class McpToolError(Exception):
    """An exception whose `str(self)` is the JSON-serialised envelope."""

    def __init__(self, payload: dict[str, Any]):
        super().__init__(json.dumps(payload))
        self.payload = payload


def _safe_message(exc: BaseException) -> str:
    text = str(exc) or exc.__class__.__name__
    # gnomAD errors are user-input shaped; trim long tracebacks/identifiers.
    return text[:240]


def _classify(exc: BaseException) -> tuple[str, bool, str | None, dict[str, Any] | None]:
    """Return (error_code, retryable, fallback_tool, fallback_args)."""

    if isinstance(exc, DataNotFoundError):
        return "not_found", False, "search_genes", None
    if isinstance(exc, ValueError):
        return "validation_failed", False, "get_server_capabilities", None
    if isinstance(exc, GnomadApiError):
        return "upstream_unavailable", True, None, None
    if isinstance(exc, TimeoutError):
        return "upstream_unavailable", True, None, None
    return "internal_error", False, None, None


def _recovery_text(error_code: str, fallback_tool: str | None) -> str:
    if error_code == "not_found":
        return (
            "Variant or gene not present in the requested dataset. "
            "Try a different dataset (gnomad_r4 default; r3/r2_1 for older builds) "
            "or use search_genes / resolve_variant_id to verify the identifier."
        )
    if error_code == "validation_failed":
        return (
            "Inputs failed validation. Check the tool schema and call "
            "get_server_capabilities for accepted dataset and population codes."
        )
    if error_code == "upstream_unavailable":
        return "gnomAD upstream API failed. Safe to retry with exponential backoff."
    return (
        f"Unexpected failure. Call {fallback_tool} for a safe entry point."
        if fallback_tool
        else ("Unexpected failure.")
    )


def _envelope_message(exc: BaseException, error_code: str) -> str:
    """Return a message safe to surface to LLM callers.

    Validation errors use a canned prefix so callers can pattern-match without
    receiving raw user input.  Internal errors are fully opaque to avoid leaking
    implementation details or sensitive values.
    """
    if error_code == "validation_failed":
        return f"Invalid input: {exc.__class__.__name__}"
    if error_code == "internal_error":
        return f"Internal error: {exc.__class__.__name__}"
    return _safe_message(exc)


def mcp_tool_error(exc: BaseException, context: McpErrorContext) -> McpToolError:
    error_code, retryable, fallback_tool, fallback_args = _classify(exc)
    payload = {
        "success": False,
        "error_code": error_code,
        "message": _envelope_message(exc, error_code),
        "retryable": retryable,
        "fallback_tool": fallback_tool,
        "fallback_args": fallback_args,
        "recovery": _recovery_text(error_code, fallback_tool),
        "_meta": {
            "tool": context.tool_name,
            "next_commands": [
                "get_server_capabilities",
                "gnomad://capabilities",
            ],
            **_RESEARCH_USE_META,
        },
    }
    return McpToolError(payload)


def record_mcp_error(*, tool_name: str, error_code: str, message: str, raw_message: str) -> None:
    _RECENT_ERRORS.append(
        {
            "tool_name": tool_name,
            "error_code": error_code,
            "message": message,
            "raw_message": raw_message[:500],
        }
    )


def get_recent_errors() -> list[dict[str, Any]]:
    return list(_RECENT_ERRORS)


def clear_recent_errors() -> None:
    _RECENT_ERRORS.clear()


async def run_mcp_tool(
    tool_name: str,
    call: Callable[[], Awaitable[dict[str, Any]]],
    *,
    context: McpErrorContext | None = None,
) -> dict[str, Any]:
    """Execute an MCP tool body, converting any exception to an envelope dict.

    Returning the envelope (rather than raising) is what pubtator-link does so
    that the LLM sees a structured failure instead of an `isError: true` MCP
    response with an opaque message.
    """

    ctx = context or McpErrorContext(tool_name=tool_name)
    try:
        return await call()
    except McpToolError as exc:
        record_mcp_error(
            tool_name=tool_name,
            error_code=exc.payload.get("error_code", "internal_error"),
            message=exc.payload.get("message", ""),
            raw_message=str(exc),
        )
        return exc.payload
    except Exception as exc:  # broad catch is the error-boundary contract
        wrapped = mcp_tool_error(exc, ctx)
        logger.warning(
            "mcp_tool_error tool=%s code=%s exc=%s",
            tool_name,
            wrapped.payload["error_code"],
            exc.__class__.__name__,
        )
        record_mcp_error(
            tool_name=tool_name,
            error_code=wrapped.payload["error_code"],
            message=wrapped.payload["message"],
            raw_message=str(exc),
        )
        return wrapped.payload
