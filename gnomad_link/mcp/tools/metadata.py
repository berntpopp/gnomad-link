"""Capabilities tool plus resource handlers."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from gnomad_link.mcp.annotations import READ_ONLY_CLOSED_WORLD
from gnomad_link.mcp.errors import run_mcp_tool
from gnomad_link.mcp.resources import get_capabilities_resource, get_usage_resource


def register_metadata_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        name="get_server_capabilities",
        title="Get gnomAD Link Capabilities",
        annotations=READ_ONLY_CLOSED_WORLD,
    )
    async def get_server_capabilities() -> dict[str, Any]:
        """Use this when a client needs supported tools, datasets, population codes, recommended workflows, or current limitations."""

        return await run_mcp_tool(
            "get_server_capabilities",
            lambda: _coro_capabilities(),
        )

    @mcp.resource("gnomad://capabilities")
    def capabilities_resource() -> dict[str, Any]:
        return get_capabilities_resource()

    @mcp.resource("gnomad://usage")
    def usage_resource() -> str:
        return get_usage_resource()


async def _coro_capabilities() -> dict[str, Any]:
    return get_capabilities_resource()
