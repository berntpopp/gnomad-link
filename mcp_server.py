#!/usr/bin/env python
"""
MCP STDIO server for gnomAD variant data.

Backwards-compatible STDIO server for AI assistants like Claude Desktop.
This is a wrapper around the unified server architecture.
"""

import asyncio
import sys

from gnomad_link.config import ServerConfig
from gnomad_link.server_manager import UnifiedServerManager


def main() -> None:
    """Start STDIO MCP server for AI assistant integration."""
    try:
        # Create STDIO configuration
        config = ServerConfig(
            transport="stdio",
            host="127.0.0.1",  # Not used for STDIO
            port=8000,  # Not used for STDIO
            mcp_path="/mcp",  # Not used for STDIO
            enable_docs=False,  # Not needed for STDIO
            log_level="WARNING",  # Minimal logging for STDIO
        )

        # Create and start server manager
        manager = UnifiedServerManager()

        # Run STDIO server
        asyncio.run(manager.start_stdio_server(config))

    except KeyboardInterrupt:
        # Graceful shutdown on interrupt
        sys.exit(0)
    except Exception as e:
        # Log errors to stderr (won't interfere with STDIO protocol)
        print(f"MCP server error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
