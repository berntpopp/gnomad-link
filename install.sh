#!/bin/bash
# Installation script for gnomAD MCP Server

echo "Installing gnomAD MCP Server..."

# Install the package in editable mode
pip install -e .

echo ""
echo "Installation complete!"
echo ""
echo "To install development dependencies, run:"
echo "  pip install -e '.[dev]'"
echo ""
echo "To start the FastAPI server:"
echo "  python server.py"
echo ""
echo "To start the MCP server:"
echo "  python mcp_server.py"