"""Task B2: every MCP response carries _meta.gnomad_release.

The constant lives in `gnomad_link.mcp.resources` as `GNOMAD_DATA_RELEASE` and
flows through `run_mcp_tool` so both success and error envelopes cite the
upstream data version alongside the existing `unsafe_for_clinical_use` flag.
"""

from __future__ import annotations

import pytest

from gnomad_link.models import VariantFrequencyResponse


class _FreqStubService:
    """Minimal FrequencyService stub returning a fixed VariantFrequencyResponse."""

    def __init__(self) -> None:
        self._response = VariantFrequencyResponse(
            variant_id="1-55051215-G-GA",
            dataset="gnomad_r4",
            exome=None,
            genome=None,
        )

    async def get_variant_frequencies(
        self, variant_id: str, dataset: str
    ) -> VariantFrequencyResponse:
        return self._response


@pytest.mark.asyncio
async def test_get_variant_frequencies_success_carries_gnomad_release() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp
    from gnomad_link.mcp.resources import GNOMAD_DATA_RELEASE

    mcp = create_gnomad_mcp(service_factory=lambda: _FreqStubService())
    result = await mcp.call_tool(
        "get_variant_frequencies",
        {"variant_id": "1-55051215-G-GA", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    assert payload.get("error_code") != "validation_failed", payload
    meta = payload.get("_meta") or {}
    assert meta.get("gnomad_release") == GNOMAD_DATA_RELEASE
    assert meta.get("gnomad_release") == "4.1.0"
    # The pre-existing research-use flag must survive.
    assert meta.get("unsafe_for_clinical_use") is True


@pytest.mark.asyncio
async def test_validation_error_carries_gnomad_release() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp
    from gnomad_link.mcp.resources import GNOMAD_DATA_RELEASE

    mcp = create_gnomad_mcp(service_factory=lambda: _FreqStubService())
    result = await mcp.call_tool(
        "get_variant_frequencies",
        {"variant_id": "not-a-variant", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    assert payload.get("success") is False
    assert payload.get("error_code") == "invalid_input"
    meta = payload.get("_meta") or {}
    assert meta.get("gnomad_release") == GNOMAD_DATA_RELEASE
    assert meta.get("gnomad_release") == "4.1.0"
    assert meta.get("unsafe_for_clinical_use") is True


@pytest.mark.asyncio
async def test_build_mismatch_error_carries_gnomad_release() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp
    from gnomad_link.mcp.resources import GNOMAD_DATA_RELEASE

    mcp = create_gnomad_mcp(service_factory=lambda: _FreqStubService())
    # 1-249100000 is beyond GRCh38 chr1 length (~248.9 Mb) so it is inferred as
    # GRCh37, but the request asks for gnomad_r4 (GRCh38) → build_mismatch.
    result = await mcp.call_tool(
        "get_variant_frequencies",
        {"variant_id": "1-249100000-A-T", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    assert payload.get("success") is False
    assert payload.get("error_code") == "invalid_input", payload
    assert payload.get("error_subtype") == "build_mismatch", payload
    meta = payload.get("_meta") or {}
    assert meta.get("gnomad_release") == GNOMAD_DATA_RELEASE
    assert meta.get("gnomad_release") == "4.1.0"
    assert meta.get("unsafe_for_clinical_use") is True


@pytest.mark.asyncio
async def test_get_server_capabilities_carries_gnomad_release() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp
    from gnomad_link.mcp.resources import GNOMAD_DATA_RELEASE

    mcp = create_gnomad_mcp(service_factory=lambda: _FreqStubService())
    result = await mcp.call_tool("get_server_capabilities", {})
    payload = result.structured_content or {}

    meta = payload.get("_meta") or {}
    assert meta.get("gnomad_release") == GNOMAD_DATA_RELEASE
    assert meta.get("gnomad_release") == "4.1.0"
