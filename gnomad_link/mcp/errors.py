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

from pydantic import ValidationError as PydanticValidationError

from gnomad_link.api import (
    DataNotFoundError,
    GnomadApiError,
    RateLimitedError,
    UpstreamInputError,
)
from gnomad_link.mcp.resources import GNOMAD_DATA_RELEASE

logger = logging.getLogger(__name__)

RECENT_MCP_ERROR_LIMIT = 50
_RECENT_ERRORS: deque[dict[str, Any]] = deque(maxlen=RECENT_MCP_ERROR_LIMIT)

# Schema-drift events live in a separate, smaller ring so LLM callers can
# distinguish business errors (the general ring) from infrastructure events
# such as upstream payloads no longer matching our declared output_schema.
RECENT_SCHEMA_DRIFT_LIMIT = 25
_RECENT_SCHEMA_DRIFT: deque[dict[str, Any]] = deque(maxlen=RECENT_SCHEMA_DRIFT_LIMIT)

# Base `_meta` block merged into every success and error envelope. The
# `gnomad_release` value lets LLM callers cite the upstream data version
# alongside the research-use disclaimer.
_BASE_META = {
    "unsafe_for_clinical_use": True,
    "gnomad_release": GNOMAD_DATA_RELEASE,
}

# Fallback tool used in validation and output-validation error envelopes.
# Points to get_gnomad_diagnostics for rich health context on error recovery.
_FALLBACK_TOOL = "get_gnomad_diagnostics"


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


class BuildMismatchError(ValueError):
    """Raised when a variant's coordinate clearly belongs to a different build than the requested dataset."""

    def __init__(self, *, variant_id: str, inferred_build: str, dataset: str):
        self.variant_id = variant_id
        self.inferred_build = inferred_build
        self.dataset = dataset
        super().__init__(
            f"{variant_id} appears to use {inferred_build} coordinates but "
            f"dataset {dataset} expects the other build."
        )


def _safe_message(exc: BaseException) -> str:
    text = str(exc) or exc.__class__.__name__
    # gnomAD errors are user-input shaped; trim long tracebacks/identifiers.
    return text[:240]


def _fallback_for(context: McpErrorContext) -> tuple[str, dict[str, Any] | None]:
    """Resolve the context-appropriate resolver tool for not_found / invalid_input.

    Variant tools point at resolve_variant_id, gene/transcript tools at
    search_genes, and everything else at the discovery entrypoint. fallback_args
    are populated from context so the LLM gets a ready-to-call next step.
    """
    # A failing variant resolver almost always received a gene symbol / free
    # text; point it at gene search rather than circularly back at itself.
    if context.tool_name in {"resolve_variant_id", "search_variants"}:
        return "search_genes", None
    # Structural-variant ids (DEL_chr1_..., BND_chr12_...) are NOT resolvable by
    # resolve_variant_id (SNV/indel only); steer to SV discovery instead.
    if context.tool_name == "get_structural_variant":
        return "search_structural_variants", None
    if context.tool_name == "search_structural_variants":
        # SV search needs a valid gene/region; help locate one.
        if context.gene_symbol or context.gene_id:
            return "search_genes", {"query": context.gene_symbol or context.gene_id}
        return "search_genes", None
    if context.variant_id:
        return "resolve_variant_id", {"query": context.variant_id}
    if context.gene_symbol or context.gene_id:
        return "search_genes", {"query": context.gene_symbol or context.gene_id}
    return "get_server_capabilities", None


def _classify(
    exc: BaseException, context: McpErrorContext
) -> tuple[str, bool, str | None, dict[str, Any] | None]:
    """Return (error_code, retryable, fallback_tool, fallback_args).

    Subclass ordering matters: DataNotFoundError, UpstreamInputError, and
    RateLimitedError all subclass GnomadApiError, so they MUST be checked before
    the generic GnomadApiError branch or they fall through to the (retryable)
    upstream_unavailable bucket. The load-bearing invariant: retryable=true means
    an identical call may later succeed; false means it never will.
    """

    if isinstance(exc, DataNotFoundError):
        tool, args = _fallback_for(context)
        return "not_found", False, tool, args
    if isinstance(exc, BuildMismatchError):
        return (
            "build_mismatch",
            False,
            "liftover_variant",
            {
                "source_variant_id": exc.variant_id,
                "reference_genome": exc.inferred_build,
            },
        )
    if isinstance(exc, UpstreamInputError):
        # Deterministic upstream rejection (wrong id shape, gene symbol to a
        # variant tool). Retrying unchanged can never succeed.
        tool, args = _fallback_for(context)
        return "invalid_input", False, tool, args
    if isinstance(exc, RateLimitedError):
        return "rate_limited", True, "get_gnomad_diagnostics", {}
    if isinstance(exc, ValueError):
        return "validation_failed", False, "get_server_capabilities", None
    if isinstance(exc, GnomadApiError):
        return "upstream_unavailable", True, "get_gnomad_diagnostics", {}
    if isinstance(exc, TimeoutError):
        return "upstream_unavailable", True, "get_gnomad_diagnostics", {}
    return "internal_error", False, "get_gnomad_diagnostics", {}


def _recovery_action(error_code: str, retryable: bool) -> str:
    """Action-typed guidance so the LLM does not infer behavior from a bare bool.

    retry_backoff (wait + retry same call) | reformulate_input (fix the id/fields,
    same tool) | switch_tool (call the fallback_tool, then the original).
    """
    if retryable:
        return "retry_backoff"
    if error_code in {"invalid_input", "validation_failed"}:
        return "reformulate_input"
    return "switch_tool"


def _recovery_text(error_code: str, fallback_tool: str | None) -> str:
    if error_code == "not_found":
        resolver = fallback_tool or "resolve_variant_id"
        return (
            "Identifier well-formed but absent in the requested dataset. This is a "
            "reformulate, not a retry: try a different dataset (gnomad_r4 default; "
            f"r3/r2_1 for older builds) or call {resolver} to verify the identifier."
        )
    if error_code == "invalid_input":
        resolver = fallback_tool or "get_server_capabilities"
        return (
            "The upstream API rejected this request as malformed (the identifier or "
            "query shape is wrong for this tool). Do not retry unchanged. Reformulate "
            f"the identifier or call {resolver} to convert free text / symbols / rsIDs "
            "into the required id."
        )
    if error_code == "rate_limited":
        return (
            "Upstream rate limit hit (HTTP 429). Safe to retry after a short delay "
            "with exponential backoff; honor any Retry-After header."
        )
    if error_code == "validation_failed":
        return (
            "Inputs failed validation. Check the tool schema and call "
            "get_server_capabilities for accepted dataset and population codes."
        )
    if error_code == "build_mismatch":
        return (
            "Variant coordinates appear to use a different reference build than "
            "the requested dataset. Run liftover_variant to convert, or switch dataset."
        )
    if error_code == "upstream_unavailable":
        return (
            "gnomAD upstream API failed transiently. Safe to retry with exponential "
            "backoff (cap attempts)."
        )
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
    if error_code == "build_mismatch":
        # The constructed message is already safe and informative for callers.
        return _safe_message(exc)
    if error_code == "validation_failed":
        return f"Invalid input: {exc.__class__.__name__}"
    if error_code == "internal_error":
        return f"Internal error: {exc.__class__.__name__}"
    return _safe_message(exc)


def _extract_field_errors(errors: list[Any]) -> list[dict[str, str]]:
    """Flatten Pydantic validation errors into {field, reason} dicts."""
    result: list[dict[str, str]] = []
    for err in errors:
        loc = err.get("loc", ())
        field_name = ".".join(str(x) for x in loc) if loc else "unknown"
        reason = err.get("msg", str(err.get("type", "invalid")))
        result.append({"field": field_name, "reason": reason})
    return result


def mcp_validation_tool_error(
    *,
    tool_name: str,
    exc: PydanticValidationError,
) -> McpToolError:
    """Build a sanitized validation failure raised before tool execution starts."""
    field_errors = _extract_field_errors(list(exc.errors()))
    payload: dict[str, Any] = {
        "success": False,
        "error_code": "validation_failed",
        "message": "Invalid MCP arguments.",
        "retryable": False,
        "recovery_action": "reformulate_input",
        "fallback_tool": _FALLBACK_TOOL,
        "fallback_args": {},
        "field_errors": field_errors,
        "recovery": (
            "Inputs failed validation. Check field_errors for details and call "
            f"{_FALLBACK_TOOL} for accepted dataset and population codes."
        ),
        "_meta": {
            "next_commands": [{"tool": _FALLBACK_TOOL, "arguments": {}}],
            **_BASE_META,
        },
    }
    return McpToolError(payload)


def install_validation_error_handler(mcp_server: Any) -> None:
    """Wrap registered tools so FastMCP argument validation returns our envelope.

    FastMCP stores tools on ``_local_provider._components`` (modern path) or the
    legacy ``_tool_manager._tools`` mapping. We probe both so the handler keeps
    working across FastMCP minor versions. Tools without a ``run`` method (e.g.
    resources or prompts that happen to share the registry) are skipped.
    """
    candidates: list[Any] = []
    local_provider = getattr(mcp_server, "_local_provider", None)
    components = getattr(local_provider, "_components", None)
    if isinstance(components, dict):
        candidates.extend(components.values())
    tool_manager = getattr(mcp_server, "_tool_manager", None)
    legacy_tools = getattr(tool_manager, "_tools", None)
    if isinstance(legacy_tools, dict):
        candidates.extend(legacy_tools.values())

    for tool in candidates:
        if not hasattr(tool, "run") or getattr(tool, "_gnomad_validation_wrapped", False):
            continue
        original_run = tool.run

        async def wrapped_run(
            arguments: dict[str, Any],
            *,
            _original_run: Callable[[dict[str, Any]], Awaitable[Any]] = original_run,
            _tool: Any = tool,
        ) -> Any:
            try:
                return await _original_run(arguments)
            except PydanticValidationError as exc:
                envelope = mcp_validation_tool_error(
                    tool_name=str(getattr(_tool, "name", "unknown")),
                    exc=exc,
                ).payload
                record_mcp_error(
                    tool_name=str(getattr(_tool, "name", "unknown")),
                    error_code="validation_failed",
                    message=envelope["message"],
                    raw_message=str(exc),
                )
                convert_result = getattr(_tool, "convert_result", None)
                if callable(convert_result):
                    return convert_result(envelope)
                return envelope

        object.__setattr__(tool, "run", wrapped_run)
        object.__setattr__(tool, "_gnomad_validation_wrapped", True)


def mcp_tool_error(exc: BaseException, context: McpErrorContext) -> McpToolError:
    error_code, retryable, fallback_tool, fallback_args = _classify(exc, context)
    payload = {
        "success": False,
        "error_code": error_code,
        "message": _envelope_message(exc, error_code),
        "retryable": retryable,
        "recovery_action": _recovery_action(error_code, retryable),
        "fallback_tool": fallback_tool,
        "fallback_args": fallback_args,
        "recovery": _recovery_text(error_code, fallback_tool),
        "_meta": {
            "tool": context.tool_name,
            "next_commands": [
                {"tool": _FALLBACK_TOOL, "arguments": {}},
            ],
            **_BASE_META,
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


def record_schema_drift(*, tool_name: str, error_field: str | None, message: str) -> None:
    """Append an output-schema-drift event to the bounded ring.

    Separate from record_mcp_error so an LLM (via get_gnomad_diagnostics) can
    distinguish business errors (not_found, upstream_unavailable,
    validation_failed) from infrastructure events (the upstream payload no
    longer matches our declared output_schema, which usually means we need to
    widen a model).
    """
    _RECENT_SCHEMA_DRIFT.append(
        {
            "tool_name": tool_name,
            "error_field": error_field,
            "message": message[:300],
        }
    )


def get_recent_schema_drift() -> list[dict[str, Any]]:
    return list(_RECENT_SCHEMA_DRIFT)


def clear_recent_schema_drift() -> None:
    _RECENT_SCHEMA_DRIFT.clear()


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
        result = await call()
        # Inject research-use meta into every successful dict response unless
        # the tool already provides _meta (e.g. search_variants deprecation note).
        if isinstance(result, dict):
            existing_meta: dict[str, Any] = result.get("_meta") or {}
            result["_meta"] = {**existing_meta, **_BASE_META}
        return result
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
