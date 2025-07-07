# MCP Server Connection Guide

## Understanding MCP Transport

The Model Context Protocol (MCP) is different from typical HTTP APIs. Here's what you need to know:

### Default: STDIO Transport

The MCP server (`mcp_server.py`) uses **STDIO transport** by default:
- **No URL**: There's no `http://localhost:8001` or similar
- **No Port**: It doesn't listen on a network port
- **Process Communication**: It reads JSON-RPC from stdin and writes to stdout

This is why you can't connect to it with a web browser or curl!

## How to Connect

### 1. Claude Desktop (Recommended)

This is the primary use case for MCP servers.

**Step 1: Find your config file**
- Mac: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

**Step 2: Add the gnomAD server**
```json
{
  "mcpServers": {
    "gnomad": {
      "command": "python",
      "args": ["C:/development/scholl-lab/GnomAD-MCP/mcp_server.py"]
    }
  }
}
```

**Step 3: Restart Claude Desktop**

**Step 4: Use the tools**
- Open Claude Desktop
- Click the tools icon (🔧)
- You should see "get_variant_allele_frequency" available

### 2. Testing with STDIO

To test the server directly:

```bash
# Terminal 1: Start the server
cd /mnt/c/development/scholl-lab/GnomAD-MCP
python mcp_server.py

# Terminal 2: Send requests
echo '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}' | python mcp_server.py
```

### 3. Using the REST API Instead

If you need HTTP access, use the FastAPI server:

```bash
# Start the REST API server
python server.py

# Access at http://localhost:8000
curl http://localhost:8000/variant/gnomad_r4/1-55039447-G-T
```

### 4. Creating an HTTP MCP Server

If you specifically need MCP over HTTP:

```python
# mcp_server_http.py already exists but needs FastMCP HTTP support
# Note: FastMCP's HTTP transport may have limitations
```

## Quick Comparison

| Feature | MCP (STDIO) | FastAPI (HTTP) |
|---------|-------------|----------------|
| URL | None | http://localhost:8000 |
| Transport | STDIO | HTTP/REST |
| Use Case | AI Assistants | Web Apps, APIs |
| Tools | MCP Tools | REST Endpoints |
| Docs | N/A | /docs |

## Troubleshooting

**"Where is the URL?"**
- There isn't one for STDIO MCP. Use Claude Desktop or the REST API.

**"How do I test it?"**
- Use Claude Desktop (best option)
- Use the FastAPI server for HTTP testing
- Send JSON-RPC messages via stdin

**"Can I use it in my web app?"**
- Use the FastAPI server (port 8000) for web applications
- MCP is designed for AI assistant integrations, not web apps

## Example Usage

### Via Claude Desktop
Once configured, you can ask Claude:
"Use the gnomAD tool to look up variant 1-55039447-G-T in dataset gnomad_r4"

### Via REST API
```bash
curl http://localhost:8000/variant/gnomad_r4/1-55039447-G-T
```

### Via Python Client
```python
import httpx

async with httpx.AsyncClient() as client:
    response = await client.get(
        "http://localhost:8000/variant/gnomad_r4/1-55039447-G-T"
    )
    data = response.json()
```