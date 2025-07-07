#!/usr/bin/env python
"""
STDIO wrapper for the gnomAD MCP server.
This allows the MCP server to work with Claude Desktop's STDIO interface.
"""
import sys

# Import the MCP server from the main server module
from server import mcp


if __name__ == "__main__":
    print("Starting gnomAD MCP server...", file=sys.stderr)
    # Run the MCP server - it handles its own async event loop
    mcp.run()
