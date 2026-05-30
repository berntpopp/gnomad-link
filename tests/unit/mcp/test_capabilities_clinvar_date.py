"""F2 + self_doc: get_server_capabilities surfaces the live ClinVar release date.

The deprecated get_clinvar_meta returned the real date while capabilities
returned null, even though we steer callers to capabilities. The async tool now
fetches clinvar_release_date best-effort into a shared process cache; the static
gnomad://capabilities resource and per-tool envelope _meta then echo the cached
date (null until the first capabilities call populates it).
"""

from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.mcp.tools import metadata as metadata_mod


class _MetaStub:
    def __init__(self, meta: dict[str, Any] | Exception) -> None:
        self._meta = meta

    async def get_clinvar_meta(self) -> dict[str, Any]:
        if isinstance(self._meta, Exception):
            raise self._meta
        return self._meta


@pytest.fixture(autouse=True)
def _clear_cache():
    metadata_mod._reset_clinvar_date_cache()
    yield
    metadata_mod._reset_clinvar_date_cache()


@pytest.mark.asyncio
async def test_capabilities_tool_surfaces_live_clinvar_date() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _MetaStub({"meta": {"clinvar_release_date": "2026-05-03"}})
    mcp = create_gnomad_mcp(service_factory=lambda: stub)
    result = await mcp.call_tool("get_server_capabilities", {})
    payload = result.structured_content or {}

    assert payload["clinvar_release_date"] == "2026-05-03"


@pytest.mark.asyncio
async def test_capabilities_tool_degrades_gracefully_when_meta_unavailable() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _MetaStub(RuntimeError("upstream down"))
    mcp = create_gnomad_mcp(service_factory=lambda: stub)
    result = await mcp.call_tool("get_server_capabilities", {})
    payload = result.structured_content or {}

    # Missing date is not a blocker: the field stays null, tool still returns caps.
    assert payload.get("clinvar_release_date") is None
    assert "datasets" in payload


def test_static_capabilities_resource_null_until_cache_populated() -> None:
    # The sync resource never fetches upstream; it is null until a capabilities
    # tool call has populated the shared cache (cleared by the autouse fixture).
    from gnomad_link.mcp.resources import get_capabilities_resource

    assert get_capabilities_resource()["clinvar_release_date"] is None


def test_capabilities_resource_reflects_cached_date() -> None:
    from gnomad_link.mcp import clinvar_date_cache
    from gnomad_link.mcp.resources import get_capabilities_resource

    clinvar_date_cache.set_cached_clinvar_release_date("2026-05-03")

    assert get_capabilities_resource()["clinvar_release_date"] == "2026-05-03"


@pytest.mark.asyncio
async def test_tool_envelope_meta_pins_clinvar_date_after_capabilities_call() -> None:
    """Once capabilities has fetched the date, every envelope _meta echoes it."""
    from gnomad_link.mcp.errors import run_mcp_tool
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _MetaStub({"meta": {"clinvar_release_date": "2026-05-03"}})
    mcp = create_gnomad_mcp(service_factory=lambda: stub)
    await mcp.call_tool("get_server_capabilities", {})

    async def ok() -> dict[str, str]:
        return {"variant_id": "1-1-A-T"}

    result = await run_mcp_tool("get_variant_frequencies", ok)

    assert result["_meta"]["clinvar_release_date"] == "2026-05-03"
