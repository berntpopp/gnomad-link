from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, ValidationError


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


def test_tool_input_error_message_is_surfaced() -> None:
    """A developer-authored ToolInputError surfaces its (safe) message verbatim."""
    from gnomad_link.mcp.errors import McpErrorContext, ToolInputError, mcp_tool_error

    err = mcp_tool_error(
        ToolInputError("Provide exactly one of gene_symbol, gene_id, or region."),
        McpErrorContext(tool_name="search_structural_variants"),
    )
    payload = json.loads(str(err))

    assert payload["error_code"] == "validation_failed"
    assert "Provide exactly one of" in payload["message"]


def test_bare_value_error_stays_redacted() -> None:
    """A bare ValueError may carry user input, so its message stays opaque."""
    from gnomad_link.mcp.errors import McpErrorContext, mcp_tool_error

    err = mcp_tool_error(
        ValueError("secret user value abc123"),
        McpErrorContext(tool_name="get_variant_frequencies"),
    )
    payload = json.loads(str(err))

    assert payload["error_code"] == "validation_failed"
    assert "abc123" not in payload["message"]
    assert payload["message"].startswith("Invalid input:")


@pytest.mark.asyncio
async def test_success_payload_sets_symmetric_success_flag() -> None:
    from gnomad_link.mcp.errors import run_mcp_tool

    async def ok() -> dict[str, str]:
        return {"variant_id": "1-1-A-T"}

    result = await run_mcp_tool("get_variant_frequencies", ok)

    assert result["success"] is True


@pytest.mark.asyncio
async def test_success_meta_echoes_dataset_and_build_when_known() -> None:
    from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool

    async def ok() -> dict[str, str]:
        return {"variant_id": "1-1-A-T"}

    result = await run_mcp_tool(
        "get_variant_frequencies",
        ok,
        context=McpErrorContext(tool_name="get_variant_frequencies", dataset="gnomad_r4"),
    )

    assert result["_meta"]["dataset"] == "gnomad_r4"
    assert result["_meta"]["reference_genome"] == "GRCh38"


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

    assert result["ok"] == "yes"
    # run_mcp_tool injects _meta on every successful dict response
    assert "_meta" in result
    assert result["_meta"]["unsafe_for_clinical_use"] is True


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


def test_mcp_tool_error_has_structured_next_commands() -> None:
    from gnomad_link.mcp.errors import McpErrorContext, mcp_tool_error

    err = mcp_tool_error(
        ValueError("bad param"),
        McpErrorContext(tool_name="get_variant_frequencies"),
    )
    payload = json.loads(str(err))
    next_commands = payload["_meta"]["next_commands"]
    assert isinstance(next_commands, list)
    assert len(next_commands) >= 1
    # Each command must be a dict with "tool" and "arguments" keys
    for cmd in next_commands:
        assert isinstance(cmd, dict), f"next_commands entry is not a dict: {cmd}"
        assert "tool" in cmd
        assert "arguments" in cmd


def _make_pydantic_validation_error() -> ValidationError:
    """Return a real PydanticValidationError for testing."""

    class _Model(BaseModel):
        dataset: str
        count: int

    try:
        _Model.model_validate({"dataset": 123, "count": "not_a_number"})
    except ValidationError as exc:
        return exc
    raise AssertionError("Expected ValidationError was not raised")  # pragma: no cover


def test_validation_handler_emits_field_errors() -> None:
    from gnomad_link.mcp.errors import mcp_validation_tool_error

    exc = _make_pydantic_validation_error()
    err = mcp_validation_tool_error(tool_name="get_variant_frequencies", exc=exc)
    payload = json.loads(str(err))

    assert payload["success"] is False
    assert payload["error_code"] == "validation_failed"
    assert "field_errors" in payload
    field_errors = payload["field_errors"]
    assert isinstance(field_errors, list)
    assert len(field_errors) >= 1
    for fe in field_errors:
        assert "field" in fe
        assert "reason" in fe
    next_commands = payload["_meta"]["next_commands"]
    assert isinstance(next_commands, list)
    assert any(isinstance(c, dict) and "tool" in c for c in next_commands)
    assert payload["_meta"]["unsafe_for_clinical_use"] is True


@pytest.mark.asyncio
async def test_success_response_carries_unsafe_for_clinical_use_meta() -> None:
    from gnomad_link.mcp.errors import run_mcp_tool

    async def good() -> dict[str, str]:
        return {"variant_id": "1-55051215-G-GA", "dataset": "gnomad_r4"}

    result = await run_mcp_tool("get_variant_frequencies", good)

    assert "_meta" in result
    assert result["_meta"]["unsafe_for_clinical_use"] is True
    # The original payload fields must not be clobbered.
    assert result["variant_id"] == "1-55051215-G-GA"


@pytest.mark.asyncio
async def test_success_response_preserves_existing_meta() -> None:
    from gnomad_link.mcp.errors import run_mcp_tool

    async def good_with_meta() -> dict[str, object]:
        return {
            "variant_id": "1-1-A-T",
            "_meta": {"next_commands": [{"tool": "get_gene_variants", "arguments": {}}]},
        }

    result = await run_mcp_tool("get_variant_frequencies", good_with_meta)

    assert result["_meta"]["unsafe_for_clinical_use"] is True
    # Existing next_commands must be preserved.
    assert any(c.get("tool") == "get_gene_variants" for c in result["_meta"]["next_commands"])


def test_output_validation_handler_returns_envelope() -> None:
    from gnomad_link.mcp.output_validation import actionable_output_validation_error

    payload = actionable_output_validation_error(
        tool_name="get_variant_frequencies",
        arguments={"variant_id": "1-55051215-G-GA"},
        message="Output validation error: 'variant_id' is a required property",
    )

    assert payload["success"] is False
    assert payload["error_code"] == "output_validation_failed"
    assert payload["error_field"] == "variant_id"
    assert payload["_meta"]["unsafe_for_clinical_use"] is True
    next_commands = payload["_meta"]["next_commands"]
    assert isinstance(next_commands, list)
    assert any(isinstance(c, dict) and c.get("tool") for c in next_commands)


# ---------------------------------------------------------------------------
# Variant ID schema tightening (Task A3): CHROM-POS-REF-ALT grammar.
# These tests exercise the in-process FastMCP client so they exercise the
# validation-error envelope path end-to-end.
# ---------------------------------------------------------------------------


class _FreqStubService:
    """Stub FrequencyService used by variant-id schema tests."""

    def __init__(self, *, frequency_response: object | None = None) -> None:
        from gnomad_link.models import VariantFrequencyResponse

        self._frequency_response = frequency_response or VariantFrequencyResponse(
            variant_id="1-55051215-G-GA",
            dataset="gnomad_r4",
            exome=None,
            genome=None,
        )

    async def get_variant_frequencies(self, variant_id: str, dataset: str) -> object:
        return self._frequency_response

    async def liftover_variant(
        self, source_variant_id: str, reference_genome: str
    ) -> list[dict[str, object]]:
        return []

    async def get_structural_variant(self, variant_id: str, dataset: str) -> dict[str, object]:
        return {
            "structural_variant": {
                "variant_id": variant_id,
                "type": "DEL",
                "chrom": "1",
                "pos": 1,
                "end": 2,
                "length": 1,
            }
        }


def _is_validation_failed(payload: dict[str, object]) -> bool:
    return (
        isinstance(payload, dict)
        and payload.get("success") is False
        and payload.get("error_code") == "validation_failed"
    )


@pytest.mark.asyncio
async def test_get_variant_frequencies_rejects_malformed_id() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=lambda: _FreqStubService())
    result = await mcp.call_tool(
        "get_variant_frequencies",
        {"variant_id": "not-a-variant", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    assert _is_validation_failed(payload)
    field_errors = payload.get("field_errors", [])
    assert any(
        fe.get("field") == "variant_id" and "pattern" in fe.get("reason", "").lower()
        for fe in field_errors
    ), f"expected pattern field_error for variant_id, got {field_errors!r}"


@pytest.mark.asyncio
async def test_get_variant_frequencies_rejects_mitochondrial_id() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=lambda: _FreqStubService())
    result = await mcp.call_tool(
        "get_variant_frequencies",
        {"variant_id": "M-7497-G-A", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    assert _is_validation_failed(payload)


@pytest.mark.asyncio
async def test_get_variant_frequencies_accepts_valid_id() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=lambda: _FreqStubService())
    result = await mcp.call_tool(
        "get_variant_frequencies",
        {"variant_id": "1-55051215-G-GA", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    # Not a validation envelope: either no error_code at all, or success is not False.
    assert payload.get("error_code") != "validation_failed", payload
    assert payload.get("success") is not False, payload


@pytest.mark.asyncio
async def test_liftover_variant_accepts_mitochondrial_id() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=lambda: _FreqStubService())
    result = await mcp.call_tool(
        "liftover_variant",
        {"source_variant_id": "MT-7497-G-A", "reference_genome": "GRCh37"},
    )
    payload = result.structured_content or {}

    assert payload.get("error_code") != "validation_failed", payload
    assert payload.get("success") is not False, payload


@pytest.mark.asyncio
async def test_get_structural_variant_rejects_malformed_id() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=lambda: _FreqStubService())
    result = await mcp.call_tool(
        "get_structural_variant",
        {"variant_id": "not-an-sv", "dataset": "gnomad_sv_r4"},
    )
    payload = result.structured_content or {}

    assert _is_validation_failed(payload)


@pytest.mark.asyncio
async def test_get_structural_variant_accepts_valid_id() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=lambda: _FreqStubService())
    result = await mcp.call_tool(
        "get_structural_variant",
        {"variant_id": "DEL_chr1_1", "dataset": "gnomad_sv_r4"},
    )
    payload = result.structured_content or {}

    assert payload.get("error_code") != "validation_failed", payload
    assert payload.get("success") is not False, payload
