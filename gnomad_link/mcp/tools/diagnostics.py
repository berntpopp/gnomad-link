"""Diagnostics tool for gnomAD Link MCP."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP

from gnomad_link.mcp.annotations import READ_ONLY_CLOSED_WORLD
from gnomad_link.mcp.errors import get_recent_errors, get_recent_schema_drift, run_mcp_tool
from gnomad_link.mcp.resources import MCP_PROTOCOL_VERSION, _server_version
from gnomad_link.services import FrequencyService


def register_diagnostics_tools(
    mcp: FastMCP,
    *,
    service_factory: Callable[[], FrequencyService],
) -> None:
    @mcp.tool(
        name="get_diagnostics",
        title="Get gnomAD Link Diagnostics",
        annotations=READ_ONLY_CLOSED_WORLD,
        tags={"metadata", "diagnostics"},
        output_schema=None,
    )
    async def get_diagnostics() -> dict[str, Any]:
        """Use this when an LLM hits repeated errors or needs server health information; returns recent error history, server version, upstream availability flag, and recent_schema_drift entries so an LLM that hit output_validation_failed can self-diagnose. Returns <1kB."""

        async def call() -> dict[str, Any]:
            recent = get_recent_errors()
            drift = get_recent_schema_drift()
            return {
                "server_version": _server_version(),
                "mcp_protocol_version": MCP_PROTOCOL_VERSION,
                "recent_errors": recent,
                "recent_error_count": len(recent),
                "recent_schema_drift": drift,
                "recent_schema_drift_count": len(drift),
                "upstream_reachable": True,  # placeholder; does not call gnomAD
                "_meta": {
                    "next_commands": [{"tool": "get_server_capabilities", "arguments": {}}],
                    "unsafe_for_clinical_use": True,
                },
            }

        return await run_mcp_tool("get_diagnostics", call)
