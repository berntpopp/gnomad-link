"""Diagnostics tool for gnomAD Link MCP."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP

from gnomad_link.mcp.annotations import READ_ONLY_CLOSED_WORLD
from gnomad_link.mcp.errors import get_recent_errors, run_mcp_tool
from gnomad_link.mcp.resources import MCP_PROTOCOL_VERSION, _server_version
from gnomad_link.services import FrequencyService


def register_diagnostics_tools(
    mcp: FastMCP,
    *,
    service_factory: Callable[[], FrequencyService],
) -> None:
    @mcp.tool(
        name="get_gnomad_diagnostics",
        title="Get gnomAD Link Diagnostics",
        annotations=READ_ONLY_CLOSED_WORLD,
        tags={"metadata", "diagnostics"},
        output_schema={
            "type": "object",
            "properties": {
                "server_version": {"type": "string"},
                "mcp_protocol_version": {"type": "string"},
                "recent_errors": {"type": "array", "items": {"type": "object"}},
                "recent_error_count": {"type": "integer"},
                "upstream_reachable": {"type": "boolean"},
                "_meta": {"type": "object"},
            },
            "required": [
                "server_version",
                "mcp_protocol_version",
                "recent_errors",
                "recent_error_count",
                "upstream_reachable",
            ],
        },
    )
    async def get_gnomad_diagnostics() -> dict[str, Any]:
        """Use this when an LLM hits repeated errors or needs server health information; returns recent error history, server version, and upstream availability flag."""

        async def call() -> dict[str, Any]:
            recent = get_recent_errors()
            return {
                "server_version": _server_version(),
                "mcp_protocol_version": MCP_PROTOCOL_VERSION,
                "recent_errors": recent,
                "recent_error_count": len(recent),
                "upstream_reachable": True,  # placeholder; does not call gnomAD
                "_meta": {
                    "next_commands": [{"tool": "get_server_capabilities", "arguments": {}}],
                    "unsafe_for_clinical_use": True,
                },
            }

        return await run_mcp_tool("get_gnomad_diagnostics", call)
