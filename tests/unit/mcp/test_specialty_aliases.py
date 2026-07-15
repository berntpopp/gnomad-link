"""Mitochondrial variant alias normalization tests.

Task A5 of the MCP Facade Polish plan: callers commonly pass `chrM-`, `MT-`,
or `chrMT-` prefixed mitochondrial variant IDs. The MCP tool must accept all
four forms (including canonical `M-`) and normalize to `M-` before invoking
the service. Completely malformed input and autosomal IDs must still produce
a validation_failed envelope.
"""

from __future__ import annotations

import pytest


class _SpyMitoService:
    """Stub FrequencyService that records the variant_id forwarded by the tool."""

    def __init__(self) -> None:
        self.last_variant_id: str | None = None
        self.last_dataset: str | None = None

    async def get_mitochondrial_variant(self, variant_id: str, dataset: str) -> dict[str, object]:
        self.last_variant_id = variant_id
        self.last_dataset = dataset
        return {"mitochondrial_variant": {"variant_id": variant_id}}


def _is_validation_failed(payload: dict[str, object]) -> bool:
    return (
        isinstance(payload, dict)
        and payload.get("success") is False
        and payload.get("error_code") == "invalid_input"
    )


@pytest.mark.asyncio
async def test_mitochondrial_accepts_chrM_alias() -> None:  # noqa: N802
    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _SpyMitoService()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "get_mitochondrial_variant",
        {"variant_id": "chrM-7497-G-A", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    assert payload.get("error_code") != "invalid_input", payload
    assert spy.last_variant_id == "M-7497-G-A"
    assert spy.last_dataset == "gnomad_r4"


@pytest.mark.asyncio
async def test_mitochondrial_accepts_MT_alias() -> None:  # noqa: N802
    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _SpyMitoService()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "get_mitochondrial_variant",
        {"variant_id": "MT-7497-G-A", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    assert payload.get("error_code") != "invalid_input", payload
    assert spy.last_variant_id == "M-7497-G-A"


@pytest.mark.asyncio
async def test_mitochondrial_accepts_chrMT_alias() -> None:  # noqa: N802
    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _SpyMitoService()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "get_mitochondrial_variant",
        {"variant_id": "chrMT-7497-G-A", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    assert payload.get("error_code") != "invalid_input", payload
    assert spy.last_variant_id == "M-7497-G-A"


@pytest.mark.asyncio
async def test_mitochondrial_accepts_canonical_form() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _SpyMitoService()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "get_mitochondrial_variant",
        {"variant_id": "M-7497-G-A", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    assert payload.get("error_code") != "invalid_input", payload
    assert spy.last_variant_id == "M-7497-G-A"


@pytest.mark.asyncio
async def test_mitochondrial_rejects_malformed() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _SpyMitoService()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "get_mitochondrial_variant",
        {"variant_id": "not-a-mito", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    assert _is_validation_failed(payload)
    assert spy.last_variant_id is None


@pytest.mark.asyncio
async def test_mitochondrial_rejects_autosomal_id() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _SpyMitoService()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "get_mitochondrial_variant",
        {"variant_id": "1-55051215-G-GA", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    assert _is_validation_failed(payload)
    assert spy.last_variant_id is None


@pytest.mark.asyncio
async def test_mitochondrial_normalization_case_insensitive() -> None:
    """Lowercase `chrm-` should still normalize to canonical `M-`."""

    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _SpyMitoService()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "get_mitochondrial_variant",
        {"variant_id": "chrm-7497-G-A", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    assert payload.get("error_code") != "invalid_input", payload
    assert spy.last_variant_id == "M-7497-G-A"
