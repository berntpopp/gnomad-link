"""Tool registration entry points for the gnomAD Link MCP facade."""

from __future__ import annotations

from collections.abc import Callable

from fastmcp import FastMCP

from gnomad_link.services import FrequencyService

from gnomad_link.mcp.tools.metadata import register_metadata_tools


def register_gnomad_tools(
    mcp: FastMCP,
    *,
    service_factory: Callable[[], FrequencyService],
) -> None:
    register_metadata_tools(mcp)
    # Data tool registrations are added in later tasks.
