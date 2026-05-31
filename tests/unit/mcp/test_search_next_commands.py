"""Structured _meta.next_commands on resolve_variant_id and search_variants.

Task 8 of MCP 9.5 correctness/eval plan:
  - resolve_variant_id success payload must carry _meta.next_commands built
    from the top hit via for_variant().
  - search_variants (deprecated alias) must carry the same _meta.next_commands
    while PRESERVING deprecated/use_instead keys and next_steps.
  - next_steps must still be present (additive, non-breaking).
  - Every next_commands entry must have a non-empty arguments dict.
"""

from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.mcp.facade import create_gnomad_mcp

# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------


class _StubService:
    """Minimal FrequencyService stub for search_next_commands tests."""

    def __init__(self, search_ids: list[str] | None = None) -> None:
        self._search_ids = search_ids if search_ids is not None else ["1-55051215-G-GA"]

    async def search_variants(self, query: str, dataset: str) -> list[str]:
        return list(self._search_ids)


def _next_commands(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return (payload.get("_meta") or {}).get("next_commands") or []


# ---------------------------------------------------------------------------
# resolve_variant_id tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_variant_id_emits_next_commands_on_success() -> None:
    """resolve_variant_id with >=1 result must emit _meta.next_commands."""
    stub = _StubService(search_ids=["1-55051215-G-GA"])
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "resolve_variant_id",
        {"query": "rs11591147", "dataset": "gnomad_r4", "enrich": False},
    )
    payload = result.structured_content or {}

    assert payload.get("success") is not False, payload
    cmds = _next_commands(payload)
    assert cmds, "_meta.next_commands must be present and non-empty on success"


@pytest.mark.asyncio
async def test_resolve_variant_id_next_commands_first_entry_is_get_variant_frequencies() -> None:
    """First next_commands entry must be get_variant_frequencies for the top hit."""
    stub = _StubService(search_ids=["1-55051215-G-GA"])
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "resolve_variant_id",
        {"query": "rs11591147", "dataset": "gnomad_r4", "enrich": False},
    )
    payload = result.structured_content or {}
    cmds = _next_commands(payload)

    assert cmds[0] == {
        "tool": "get_variant_frequencies",
        "arguments": {"variant_id": "1-55051215-G-GA", "dataset": "gnomad_r4"},
    }


@pytest.mark.asyncio
async def test_resolve_variant_id_next_commands_all_have_non_empty_arguments() -> None:
    """Every next_commands entry must have a non-empty arguments dict."""
    stub = _StubService(search_ids=["1-55051215-G-GA"])
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "resolve_variant_id",
        {"query": "rs11591147", "dataset": "gnomad_r4", "enrich": False},
    )
    payload = result.structured_content or {}
    cmds = _next_commands(payload)

    for entry in cmds:
        assert isinstance(entry.get("arguments"), dict), "arguments must be a dict"
        assert entry["arguments"], f"arguments must be non-empty for {entry['tool']!r}"


@pytest.mark.asyncio
async def test_resolve_variant_id_next_steps_still_present() -> None:
    """next_steps must still be present and non-empty (additive/non-breaking)."""
    stub = _StubService(search_ids=["1-55051215-G-GA"])
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "resolve_variant_id",
        {"query": "rs11591147", "dataset": "gnomad_r4", "enrich": False},
    )
    payload = result.structured_content or {}

    next_steps = payload.get("next_steps")
    assert next_steps, "next_steps must still be present (non-breaking)"
    assert isinstance(next_steps, list) and len(next_steps) > 0


@pytest.mark.asyncio
async def test_resolve_variant_id_no_next_commands_when_empty_results() -> None:
    """When results is empty, _meta.next_commands must not be present."""
    stub = _StubService(search_ids=[])
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "resolve_variant_id",
        {"query": "nomatch", "dataset": "gnomad_r4", "enrich": False},
    )
    payload = result.structured_content or {}

    cmds = _next_commands(payload)
    assert cmds == [], "_meta.next_commands must be absent when results is empty"


@pytest.mark.asyncio
async def test_resolve_variant_id_next_commands_uses_top_hit() -> None:
    """next_commands must reference the FIRST result, not a later one."""
    stub = _StubService(search_ids=["2-222-A-T", "3-333-G-C"])
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "resolve_variant_id",
        {"query": "rs999", "dataset": "gnomad_r4", "enrich": False},
    )
    payload = result.structured_content or {}
    cmds = _next_commands(payload)

    assert cmds[0]["arguments"]["variant_id"] == "2-222-A-T"


# ---------------------------------------------------------------------------
# search_variants (deprecated alias) tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_variants_emits_next_commands_on_success() -> None:
    """search_variants with >=1 result must emit _meta.next_commands."""
    stub = _StubService(search_ids=["1-55051215-G-GA"])
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "search_variants",
        {"query": "rs11591147", "dataset": "gnomad_r4", "enrich": False},
    )
    payload = result.structured_content or {}

    assert payload.get("success") is not False, payload
    cmds = _next_commands(payload)
    assert cmds, "_meta.next_commands must be present and non-empty on success"


@pytest.mark.asyncio
async def test_search_variants_next_commands_first_entry_is_get_variant_frequencies() -> None:
    """First next_commands entry must be get_variant_frequencies for the top hit."""
    stub = _StubService(search_ids=["1-55051215-G-GA"])
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "search_variants",
        {"query": "rs11591147", "dataset": "gnomad_r4", "enrich": False},
    )
    payload = result.structured_content or {}
    cmds = _next_commands(payload)

    assert cmds[0] == {
        "tool": "get_variant_frequencies",
        "arguments": {"variant_id": "1-55051215-G-GA", "dataset": "gnomad_r4"},
    }


@pytest.mark.asyncio
async def test_search_variants_preserves_deprecated_and_use_instead() -> None:
    """search_variants must keep deprecated=True and use_instead in _meta."""
    stub = _StubService(search_ids=["1-55051215-G-GA"])
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "search_variants",
        {"query": "rs11591147", "dataset": "gnomad_r4", "enrich": False},
    )
    payload = result.structured_content or {}
    meta = payload.get("_meta") or {}

    assert meta.get("deprecated") is True, "_meta.deprecated must be True"
    assert meta.get("use_instead") == "resolve_variant_id", "_meta.use_instead must be preserve"


@pytest.mark.asyncio
async def test_search_variants_next_steps_still_present() -> None:
    """next_steps must still be present (additive/non-breaking)."""
    stub = _StubService(search_ids=["1-55051215-G-GA"])
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "search_variants",
        {"query": "rs11591147", "dataset": "gnomad_r4", "enrich": False},
    )
    payload = result.structured_content or {}

    next_steps = payload.get("next_steps")
    assert next_steps, "next_steps must still be present (non-breaking)"
    assert isinstance(next_steps, list) and len(next_steps) > 0


@pytest.mark.asyncio
async def test_search_variants_next_commands_all_have_non_empty_arguments() -> None:
    """Every next_commands entry must have a non-empty arguments dict."""
    stub = _StubService(search_ids=["1-55051215-G-GA"])
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "search_variants",
        {"query": "rs11591147", "dataset": "gnomad_r4", "enrich": False},
    )
    payload = result.structured_content or {}
    cmds = _next_commands(payload)

    for entry in cmds:
        assert isinstance(entry.get("arguments"), dict), "arguments must be a dict"
        assert entry["arguments"], f"arguments must be non-empty for {entry['tool']!r}"
