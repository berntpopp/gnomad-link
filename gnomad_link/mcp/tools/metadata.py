"""Capabilities tool plus resource handlers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP
from mcp.types import Annotations

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.clinvar_date_cache import (
    has_cached_clinvar_release_date,
    reset_clinvar_date_cache,
    set_cached_clinvar_release_date,
)
from gnomad_link.mcp.errors import run_mcp_tool
from gnomad_link.mcp.provenance import get_citations_resource
from gnomad_link.mcp.resources import (
    RESEARCH_USE_NOTICE,
    get_capabilities_resource,
    get_reference_resource,
    get_usage_resource,
)
from gnomad_link.services import FrequencyService

_RESOURCE_ANNOTATIONS = Annotations(audience=["assistant"], priority=1.0)


def register_metadata_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="get_server_capabilities",
        title="Get gnomAD Link Capabilities",
        annotations=READ_ONLY_OPEN_WORLD,
        tags={"metadata"},
    )
    async def get_server_capabilities() -> dict[str, Any]:
        """Use this when a client needs supported tools, datasets, population codes, recommended workflows, the live ClinVar release date, or current limitations. Returns ~7kB."""

        return await run_mcp_tool(
            "get_server_capabilities",
            lambda: _coro_capabilities(service_factory),
        )

    @mcp.resource(
        "gnomad://capabilities",
        annotations=_RESOURCE_ANNOTATIONS,
        mime_type="application/json",
    )
    def capabilities_resource() -> dict[str, Any]:
        return get_capabilities_resource()

    @mcp.resource("gnomad://usage", annotations=_RESOURCE_ANNOTATIONS)
    def usage_resource() -> str:
        return get_usage_resource()

    @mcp.resource(
        "gnomad://reference",
        annotations=_RESOURCE_ANNOTATIONS,
        mime_type="application/json",
    )
    def reference_resource() -> dict[str, Any]:
        # Detailed error taxonomy, truncation contract, and field/unit glossary,
        # kept out of the always-read capabilities doc.
        return get_reference_resource()

    @mcp.resource(
        "gnomad://research-use",
        annotations=_RESOURCE_ANNOTATIONS,
        mime_type="application/json",
    )
    def research_use_resource() -> dict[str, Any]:
        return {"notice": RESEARCH_USE_NOTICE}

    @mcp.resource(
        "gnomad://citations",
        annotations=_RESOURCE_ANNOTATIONS,
        mime_type="application/json",
    )
    def citations_resource() -> dict[str, Any]:
        # Full carrier-frequency citations + assumptions, referenced by the
        # `citations_ref` pointer the carrier tools emit in compact mode.
        return get_citations_resource()


async def _clinvar_release_date(service_factory: Callable[[], FrequencyService]) -> str | None:
    """Best-effort live ClinVar release date, cached for the process lifetime.

    Writes to the shared leaf cache so per-tool error/success envelopes and the
    gnomad://capabilities resource can echo the same date without an import cycle.
    """
    if has_cached_clinvar_release_date():
        from gnomad_link.mcp.clinvar_date_cache import get_cached_clinvar_release_date

        return get_cached_clinvar_release_date()
    try:
        meta = await service_factory().get_clinvar_meta()
    except Exception:
        # A missing ClinVar date is not a blocker; do not cache the failure.
        return None
    date = (meta.get("meta") or {}).get("clinvar_release_date") if isinstance(meta, dict) else None
    set_cached_clinvar_release_date(date)
    return date


async def _coro_capabilities(service_factory: Callable[[], FrequencyService]) -> dict[str, Any]:
    # Fetch first so the cache is populated; get_capabilities_resource() then
    # reads the cached date directly.
    await _clinvar_release_date(service_factory)
    return get_capabilities_resource()


def _reset_clinvar_date_cache() -> None:
    """Test helper: clear the process-level ClinVar-date cache."""
    reset_clinvar_date_cache()
