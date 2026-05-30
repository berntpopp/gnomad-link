"""F2: get_server_capabilities surfaces the live ClinVar release date.

The deprecated get_clinvar_meta returned the real date while capabilities
returned null, even though we steer callers to capabilities. The async tool now
enriches clinvar_release_date best-effort (cached), while the static
gnomad://capabilities resource stays null.
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


def test_static_capabilities_resource_stays_null() -> None:
    # The sync resource cannot fetch upstream; it intentionally keeps the field null.
    from gnomad_link.mcp.resources import get_capabilities_resource

    assert get_capabilities_resource()["clinvar_release_date"] is None
