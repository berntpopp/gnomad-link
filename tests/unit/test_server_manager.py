"""Unit tests for unified server MCP wiring."""

from pathlib import Path


def test_unified_server_mounts_fastmcp_app_at_configured_path() -> None:
    """FastMCP http_app defaults to /mcp, so mounted apps must use / internally."""
    source = Path("gnomad_link/server_manager.py").read_text(encoding="utf-8")

    assert 'mcp_http_app = self.mcp.http_app(path="/")' in source
    assert "self._compose_mcp_lifespan(self.app, mcp_http_app)" in source
    assert "self.app.mount(config.mcp_path, mcp_http_app)" in source
    assert "self.app.mount(config.mcp_path, self.mcp.http_app())" not in source
