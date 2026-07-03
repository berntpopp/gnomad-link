"""Locks the ratified GeneFoundry Response-Envelope Standard v1 (flat banner)
at this backend's MCP wrapper boundary. Adapted from clingen-link (the fleet
reference, PR #20). SUCCESS -> {success, results|result, _meta(unsafe_for_clinical_use)};
FAILURE -> flat {success:False, error_code, message, retryable, recovery_action,
_meta{tool, unsafe_for_clinical_use}}.

gnomad-link was already conformant to the standard prior to this test; this file
adds regression coverage only, with no behavior change to gnomad_link/mcp/errors.py.
"""

from __future__ import annotations

import pytest

from gnomad_link.api import DataNotFoundError
from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool

# get_variant_frequencies is a real registered tool (see
# gnomad_link/mcp/tools/variants.py), used purely as a representative tool_name
# for exercising the wrapper in isolation.
_TOOL_NAME = "get_variant_frequencies"


@pytest.mark.asyncio
async def test_success_envelope_matches_response_envelope_standard_v1() -> None:
    async def call() -> dict[str, object]:
        return {"results": [{"id": "x"}]}

    result = await run_mcp_tool(_TOOL_NAME, call)

    assert result["success"] is True
    assert result["results"] == [{"id": "x"}]
    assert result["_meta"]["unsafe_for_clinical_use"] is True


@pytest.mark.asyncio
async def test_single_item_result_key_is_preserved() -> None:
    async def call() -> dict[str, object]:
        return {"result": {"id": "x"}}

    result = await run_mcp_tool(_TOOL_NAME, call)

    assert result["success"] is True
    assert result["result"] == {"id": "x"}
    assert result["_meta"]["unsafe_for_clinical_use"] is True


@pytest.mark.asyncio
async def test_error_envelope_is_flat_not_a_bare_exception() -> None:
    async def call() -> dict[str, object]:
        raise DataNotFoundError("not found")

    result = await run_mcp_tool(
        _TOOL_NAME,
        call,
        context=McpErrorContext(tool_name=_TOOL_NAME),
    )

    assert result["success"] is False
    assert isinstance(result["error_code"], str) and result["error_code"]
    assert isinstance(result["message"], str) and result["message"]
    assert isinstance(result["retryable"], bool)
    assert isinstance(result["recovery_action"], str)
    assert "error" not in result  # flat, not nested
    assert result["_meta"]["tool"] == _TOOL_NAME
    assert result["_meta"]["unsafe_for_clinical_use"] is True
