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

from fastmcp.exceptions import ValidationError as FastMCPValidationError
from pydantic import ValidationError as PydanticValidationError

from gnomad_link.api import (
    DataNotFoundError,
    GnomadApiError,
    RateLimitedError,
    UpstreamInputError,
)
from gnomad_link.config import settings
from gnomad_link.mcp.clinvar_date_cache import get_cached_clinvar_release_date
from gnomad_link.mcp.resources import GNOMAD_DATA_RELEASE
from gnomad_link.mcp.untrusted_content import UntrustedTextLimitError, sanitize_message

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
# Points to get_diagnostics for rich health context on error recovery.
_FALLBACK_TOOL = "get_diagnostics"


@dataclass
class McpErrorContext:
    """Per-call context passed to the error builder so envelopes can suggest fallbacks."""

    tool_name: str
    variant_id: str | None = None
    gene_id: str | None = None
    gene_symbol: str | None = None
    region: str | None = None
    dataset: str | None = None
    query: str | None = None
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


class ToolInputError(ValueError):
    """A local, pre-upstream validation failure whose message is developer-authored.

    A bare ``ValueError`` may carry raw user input, so its message is redacted in
    the envelope. The strings raised by our own guard sites contain no user
    VALUES -- only static guidance or parameter NAMES -- so a ``ToolInputError``
    message is safe to surface verbatim (capped by ``_safe_message``). It still
    classifies as ``validation_failed`` because it subclasses ``ValueError``.
    """


# Maps each dataset to its reference build so error/success envelopes can echo a
# self-contained provenance pointer (which release + which build the call hit).
_DATASET_BUILD = {
    "gnomad_r2_1": "GRCh37",
    "gnomad_r3": "GRCh38",
    "gnomad_r4": "GRCh38",
    "gnomad_sv_r2_1": "GRCh37",
    "gnomad_sv_r4": "GRCh38",
}


def _provenance_meta(context: McpErrorContext | None = None) -> dict[str, Any]:
    """Base ``_meta`` provenance merged into every success and error envelope.

    Always carries the research-use flag and gnomAD release. When the call's
    dataset is known it also echoes the dataset and derived reference build, so
    the provenance pointer is self-contained even on an error envelope.
    """
    meta: dict[str, Any] = dict(_BASE_META)
    # Once the first capabilities call has fetched it, pin the ClinVar release on
    # every envelope so an LLM citing a ClinVar classification can name the
    # version that produced it. Omitted while still unknown to avoid null noise.
    clinvar_date = get_cached_clinvar_release_date()
    if clinvar_date is not None:
        meta["clinvar_release_date"] = clinvar_date
    if context is not None and context.dataset:
        meta["dataset"] = context.dataset
        build = _DATASET_BUILD.get(context.dataset)
        if build is not None:
            meta["reference_genome"] = build
    return meta


def _safe_message(exc: BaseException) -> str:
    text = str(exc) or exc.__class__.__name__
    # Strip the fence's forbidden control/zero-width/bidi/NUL code points and cap
    # length (240): a caller-visible message must never carry code points a
    # hostile upstream (or a caller-influenced 4xx/5xx body) could smuggle in.
    # Upstream response bodies are additionally severed at the GraphQL client, so
    # this closes the residual code-point surface for every message path that
    # returns a raw exception string.
    return sanitize_message(text)


def _fallback_for(context: McpErrorContext) -> tuple[str, dict[str, Any] | None]:
    """Resolve the context-appropriate resolver tool for not_found / invalid_input.

    Variant tools point at resolve_variant_id, gene/transcript tools at
    search_genes, and everything else at the discovery entrypoint. fallback_args
    are populated from context so the LLM gets a ready-to-call next step.
    """
    # A failing variant resolver almost always received a gene symbol / free
    # text; point it at gene search rather than circularly back at itself.
    if context.tool_name in {"resolve_variant_id", "search_variants"}:
        return "search_genes", ({"query": context.query} if context.query else None)
    # Structural-variant ids (DEL_chr1_..., BND_chr12_...) are NOT resolvable by
    # resolve_variant_id (SNV/indel only); steer to SV discovery instead.
    if context.tool_name == "get_structural_variant":
        return "search_structural_variants", None
    if context.tool_name == "search_structural_variants":
        # SV search needs a valid gene/region; help locate one.
        if context.gene_symbol or context.gene_id:
            return "search_genes", {"query": context.gene_symbol or context.gene_id}
        return "search_genes", None
    # M-POS-REF-ALT ids are NOT resolvable by resolve_variant_id (SNV/indel
    # only), so a mito not_found must not route there; point at capabilities for
    # the valid mitochondrial datasets instead.
    if context.tool_name == "get_mitochondrial_variant":
        return "get_server_capabilities", None
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
            "compute_variant_liftover",
            {
                "source_variant_id": exc.variant_id,
                "source_genome": exc.inferred_build,
            },
        )
    if isinstance(exc, UpstreamInputError):
        # Deterministic upstream rejection (wrong id shape, gene symbol to a
        # variant tool). Retrying unchanged can never succeed.
        tool, args = _fallback_for(context)
        return "invalid_input", False, tool, args
    if isinstance(exc, RateLimitedError):
        return "rate_limited", True, "get_diagnostics", {}
    # UntrustedTextLimitError subclasses ValueError, so it MUST be checked before
    # the generic ValueError branch or a fenced-response ceiling breach would be
    # mislabeled as caller input validation. It is a response-side limit
    # (Response-Envelope v1.1 object/byte ceiling), not bad caller input: the
    # caller recovers by shrinking the response (e.g. a smaller submissions_limit).
    if isinstance(exc, UntrustedTextLimitError):
        return "response_limit_exceeded", False, None, None
    if isinstance(exc, ValueError):
        return "validation_failed", False, "get_server_capabilities", None
    if isinstance(exc, GnomadApiError):
        return "upstream_unavailable", True, "get_diagnostics", {}
    if isinstance(exc, TimeoutError):
        return "upstream_unavailable", True, "get_diagnostics", {}
    return "internal_error", False, "get_diagnostics", {}


def _recovery_action(error_code: str, retryable: bool) -> str:
    """Action-typed guidance so the LLM does not infer behavior from a bare bool.

    retry_backoff (wait + retry same call) | reformulate_input (fix the id/fields,
    same tool) | switch_tool (call the fallback_tool, then the original).
    """
    if retryable:
        return "retry_backoff"
    if error_code in {"invalid_input", "validation_failed", "response_limit_exceeded"}:
        return "reformulate_input"
    return "switch_tool"


def _recovery_text(error_code: str, fallback_tool: str | None, tool_name: str | None = None) -> str:
    if error_code == "not_found":
        if tool_name in {"get_structural_variant", "search_structural_variants"}:
            return (
                "Identifier well-formed but absent in the requested SV dataset. This is "
                "a reformulate, not a retry: try the other SV dataset (gnomad_sv_r4 "
                "default, GRCh38; gnomad_sv_r2_1 for GRCh37) or call "
                "search_structural_variants to locate a valid structural-variant id."
            )
        if tool_name == "get_mitochondrial_variant":
            return (
                "Identifier well-formed but absent in the requested dataset. This is a "
                "reformulate, not a retry: mitochondrial variants are in gnomad_r4 "
                "(default) and gnomad_r3 only -- not gnomad_r2_1. Confirm the "
                "M-POS-REF-ALT id and dataset."
            )
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
        floor = settings.GNOMAD_QUEUE_WAIT_TIMEOUT
        return (
            "Upstream rate limit (HTTP 429) or local concurrency saturation. Safe to "
            f"retry after backing off exponentially (start around {floor}s) and reduce "
            "the number of concurrent calls to this server."
        )
    if error_code == "validation_failed":
        return (
            "Inputs failed validation. Check the tool schema and call "
            "get_server_capabilities for accepted dataset and population codes."
        )
    if error_code == "response_limit_exceeded":
        return (
            "The response's fenced untrusted-text objects exceeded a Response-Envelope "
            "v1.1 ceiling (object count or total bytes). This is a reformulate, not a "
            "retry: request fewer records (e.g. a smaller submissions_limit) so the "
            "emitted payload stays under the limit."
        )
    if error_code == "build_mismatch":
        return (
            "Variant coordinates appear to use a different reference build than "
            "the requested dataset. Run compute_variant_liftover to convert, or switch dataset."
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
    if isinstance(exc, ToolInputError):
        # Developer-authored guard string (static or parameter NAMES only, no user
        # values), so it is safe to surface verbatim instead of redacting.
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
        # A pydantic ``msg`` is framework-authored, but a custom "Value error, ..."
        # can embed developer/validator text; sanitize the caller-visible reason
        # so no forbidden code point can reach the arg-validation frame.
        result.append({"field": field_name, "reason": sanitize_message(reason)})
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
            **_provenance_meta(),
        },
    }
    return McpToolError(payload)


def _validation_result(tool: Any, exc: PydanticValidationError) -> Any:
    """Convert a tool argument failure to the public validation envelope."""
    tool_name = str(getattr(tool, "name", "unknown"))
    envelope = mcp_validation_tool_error(tool_name=tool_name, exc=exc).payload
    record_mcp_error(
        tool_name=tool_name,
        error_code="validation_failed",
        exc_type=type(exc).__name__,
    )
    convert_result = getattr(tool, "convert_result", None)
    if callable(convert_result):
        return convert_result(envelope)
    return envelope


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
            except FastMCPValidationError as exc:
                # FastMCP 3.4.4 wraps pre-body TypeAdapter argument failures this
                # way; Pydantic errors raised by the tool body use _ToolBodyError.
                cause = exc.__cause__
                if not isinstance(cause, PydanticValidationError):
                    raise
                return _validation_result(_tool, cause)
            except PydanticValidationError as exc:
                return _validation_result(_tool, exc)

        object.__setattr__(tool, "run", wrapped_run)
        object.__setattr__(tool, "_gnomad_validation_wrapped", True)


def mcp_tool_error(exc: BaseException, context: McpErrorContext) -> McpToolError:
    error_code, retryable, fallback_tool, fallback_args = _classify(exc, context)
    # next_commands must agree with the classified fallback: prepend the
    # task-advancing resolver when there is one, keeping diagnostics as the
    # secondary entry. For retryable codes fallback_tool is already diagnostics,
    # so the guard collapses to a single diagnostics entry (retry, not switch).
    next_commands: list[dict[str, Any]] = []
    if fallback_tool and fallback_tool != _FALLBACK_TOOL:
        next_commands.append({"tool": fallback_tool, "arguments": fallback_args or {}})
    next_commands.append({"tool": _FALLBACK_TOOL, "arguments": {}})
    payload = {
        "success": False,
        "error_code": error_code,
        "message": _envelope_message(exc, error_code),
        "retryable": retryable,
        "recovery_action": _recovery_action(error_code, retryable),
        "fallback_tool": fallback_tool,
        "fallback_args": fallback_args,
        "recovery": _recovery_text(error_code, fallback_tool, context.tool_name),
        "_meta": {
            "tool": context.tool_name,
            "next_commands": next_commands,
            **_provenance_meta(context),
        },
    }
    return McpToolError(payload)


def record_mcp_error(*, tool_name: str, error_code: str, exc_type: str) -> None:
    """Append a non-PII error record to the process-global ring (finding M4).

    The ring is returned verbatim by ``get_diagnostics`` to any caller, so it must
    NOT retain raw exception text (``message`` / ``raw_message``): a not_found or
    upstream error embeds the caller's processed variables (variant coordinates,
    rejected input) and would leak cross-session. Only the tool name, classified
    error code, and exception CLASS name are non-identifying; the raw text still
    reaches operators via the structured log line, not the caller-facing ring.
    """
    _RECENT_ERRORS.append(
        {
            "tool_name": tool_name,
            "error_code": error_code,
            "exc_type": exc_type,
        }
    )


def get_recent_errors() -> list[dict[str, Any]]:
    return list(_RECENT_ERRORS)


def clear_recent_errors() -> None:
    _RECENT_ERRORS.clear()


def record_schema_drift(*, tool_name: str, error_field: str | None) -> None:
    """Append a non-PII output-schema-drift event to the bounded ring.

    Separate from record_mcp_error so an LLM (via get_diagnostics) can
    distinguish business errors (not_found, upstream_unavailable,
    validation_failed) from infrastructure events (the upstream payload no
    longer matches our declared output_schema, which usually means we need to
    widen a model).

    The raw SDK validation ``message`` is deliberately NOT stored (finding M4):
    get_diagnostics returns this ring to any caller, and the raw text can embed
    the upstream payload / caller input. Only the tool name and the parsed
    ``error_field`` (a property name from OUR declared output schema, never
    caller input) are non-identifying.
    """
    _RECENT_SCHEMA_DRIFT.append(
        {
            "tool_name": tool_name,
            "error_field": error_field,
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
        # A symmetric success:true flag lets callers branch on `success` instead
        # of special-casing `is False`.
        if isinstance(result, dict):
            result.setdefault("success", True)
            existing_meta: dict[str, Any] = result.get("_meta") or {}
            result["_meta"] = {**existing_meta, **_provenance_meta(ctx)}
        return result
    except McpToolError as exc:
        record_mcp_error(
            tool_name=tool_name,
            error_code=exc.payload.get("error_code", "internal_error"),
            exc_type=type(exc).__name__,
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
            exc_type=type(exc).__name__,
        )
        return wrapped.payload
