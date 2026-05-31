"""Task 10: resolve/search error fallback must carry the original query.

When resolve_variant_id or search_variants fail with not_found or
invalid_input, the fallback next_commands entry must be:
  {"tool": "search_genes", "arguments": {"query": <original query>}}
NOT empty arguments -- the caller cannot execute a search_genes call
without a query.
"""

from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.api import DataNotFoundError, UpstreamInputError
from gnomad_link.mcp.facade import create_gnomad_mcp

# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------


class _ErrorStubService:
    """Stub FrequencyService that always raises on search_variants."""

    def __init__(self, *, exc: Exception) -> None:
        self._exc = exc

    async def search_variants(self, query: str, dataset: str) -> list[str]:
        raise self._exc


def _first_search_genes_cmd(
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    """Return the first search_genes next_command entry, or None."""
    cmds: list[dict[str, Any]] = (payload.get("_meta") or {}).get("next_commands") or []
    for cmd in cmds:
        if cmd.get("tool") == "search_genes":
            return cmd
    return None


# ---------------------------------------------------------------------------
# resolve_variant_id error fallback tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_variant_id_not_found_fallback_carries_query() -> None:
    """not_found from resolve_variant_id must produce search_genes with the query."""
    query = "BRCA2 fragment"
    stub = _ErrorStubService(exc=DataNotFoundError(f"{query!r} not found"))
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "resolve_variant_id",
        {"query": query, "dataset": "gnomad_r4", "enrich": False},
    )
    payload: dict[str, Any] = result.structured_content or {}

    assert payload.get("success") is False
    assert payload.get("error_code") == "not_found"
    cmd = _first_search_genes_cmd(payload)
    assert cmd is not None, f"expected a search_genes entry in next_commands; got {payload!r}"
    assert cmd["arguments"] == {"query": query}, (
        f"expected arguments={{'query': {query!r}}}, got {cmd['arguments']!r}"
    )


@pytest.mark.asyncio
async def test_resolve_variant_id_invalid_input_fallback_carries_query() -> None:
    """invalid_input from resolve_variant_id must produce search_genes with the query."""
    query = "rsBOGUS"
    stub = _ErrorStubService(
        exc=UpstreamInputError("Unrecognized query. Search by variant ID, rsID, or ClinVar ID.")
    )
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "resolve_variant_id",
        {"query": query, "dataset": "gnomad_r4", "enrich": False},
    )
    payload: dict[str, Any] = result.structured_content or {}

    assert payload.get("success") is False
    assert payload.get("error_code") == "invalid_input"
    cmd = _first_search_genes_cmd(payload)
    assert cmd is not None, f"expected a search_genes entry in next_commands; got {payload!r}"
    assert cmd["arguments"] == {"query": query}, (
        f"expected arguments={{'query': {query!r}}}, got {cmd['arguments']!r}"
    )


# ---------------------------------------------------------------------------
# search_variants error fallback tests (deprecated alias)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_variants_not_found_fallback_carries_query() -> None:
    """not_found from search_variants must produce search_genes with the query."""
    query = "BRCA2 fragment"
    stub = _ErrorStubService(exc=DataNotFoundError(f"{query!r} not found"))
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "search_variants",
        {"query": query, "dataset": "gnomad_r4", "enrich": False},
    )
    payload: dict[str, Any] = result.structured_content or {}

    assert payload.get("success") is False
    assert payload.get("error_code") == "not_found"
    cmd = _first_search_genes_cmd(payload)
    assert cmd is not None, f"expected a search_genes entry in next_commands; got {payload!r}"
    assert cmd["arguments"] == {"query": query}, (
        f"expected arguments={{'query': {query!r}}}, got {cmd['arguments']!r}"
    )


@pytest.mark.asyncio
async def test_search_variants_invalid_input_fallback_carries_query() -> None:
    """invalid_input from search_variants must produce search_genes with the query."""
    query = "rsBOGUS"
    stub = _ErrorStubService(
        exc=UpstreamInputError("Unrecognized query. Search by variant ID, rsID, or ClinVar ID.")
    )
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "search_variants",
        {"query": query, "dataset": "gnomad_r4", "enrich": False},
    )
    payload: dict[str, Any] = result.structured_content or {}

    assert payload.get("success") is False
    assert payload.get("error_code") == "invalid_input"
    cmd = _first_search_genes_cmd(payload)
    assert cmd is not None, f"expected a search_genes entry in next_commands; got {payload!r}"
    assert cmd["arguments"] == {"query": query}, (
        f"expected arguments={{'query': {query!r}}}, got {cmd['arguments']!r}"
    )
