# MCP Server Connection Guide

## Understanding the Unified Server

The gnomAD server now provides both REST API and MCP interfaces through a single unified application:

- **Single Process**: One server provides both interfaces
- **Shared Resources**: Both interfaces use the same cache and services
- **HTTP-Based**: The MCP interface is available via HTTP at `/mcp`

## How to Connect

### 1. Start the Unified Server

```bash
# Navigate to the project directory
cd /mnt/c/development/gnomad-link

# Start the server (development mode)
python server.py

# Or production mode
uvicorn server:app --host 0.0.0.0 --port 8000
```

The server now provides:
- REST API at http://localhost:8000/
- MCP interface at http://localhost:8000/mcp

### 2. Claude Desktop Configuration (HTTP)

For Claude Desktop configurations that support HTTP endpoints:

**Step 1: Find your config file**
- Mac: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

**Step 2: Add the gnomAD server (HTTP endpoint)**
```json
{
  "mcpServers": {
    "gnomad": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

**Step 3: Restart Claude Desktop**

**Step 4: Use the tools**
- Open Claude Desktop
- The gnomAD tools should be available:
  - `get_variant_allele_frequency`
  - `get_gene_summary`

### 3. Alternative: STDIO Configuration

If your Claude Desktop doesn't support HTTP endpoints yet, you can create a wrapper script:

```python
# mcp_stdio_wrapper.py
import sys
import asyncio
import httpx
import json

async def bridge_stdio_to_http():
    """Bridge STDIO to HTTP MCP endpoint"""
    async with httpx.AsyncClient() as client:
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            
            # Forward to HTTP endpoint
            response = await client.post(
                "http://localhost:8000/mcp",
                content=line,
                headers={"Content-Type": "application/json"}
            )
            
            # Return response
            sys.stdout.write(response.text)
            sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(bridge_stdio_to_http())
```

Then use this configuration:
```json
{
  "mcpServers": {
    "gnomad": {
      "command": "python",
      "args": ["/path/to/mcp_stdio_wrapper.py"]
    }
  }
}
```

### 4. Using the REST API

The REST API remains available at the root path:

```bash
# Get variant frequency data
curl http://localhost:8000/variant/1-55039447-G-T?dataset=gnomad_r4

# Access interactive docs
open http://localhost:8000/docs

# Check health
curl http://localhost:8000/health

# Get cache stats
curl http://localhost:8000/cache/stats
```

## Available Interfaces

| Interface | URL | Purpose | Access Method |
|-----------|-----|---------|---------------|
| REST API | http://localhost:8000/ | Web applications, direct API calls | HTTP/REST |
| MCP Tools | http://localhost:8000/mcp | AI assistants, language models | MCP over HTTP |
| API Docs | http://localhost:8000/docs | Interactive documentation | Web browser |

## Available MCP Tools

1. **get_variant_allele_frequency**
   - Get population frequency data for a genetic variant
   - Parameters:
     - `variant_id`: e.g., "1-55039447-G-T"
     - `dataset`: e.g., "gnomad_r4" (optional, defaults to r4)

2. **get_gene_summary**
   - Get gene information including pLI score
   - Parameters:
     - `gene_symbol`: e.g., "BRCA1", "TP53"

## Example Usage

### Via Claude Desktop
Once configured, you can ask Claude:
"Use the gnomAD tool to look up variant 1-55039447-G-T in dataset gnomad_r4"

### Via REST API
```bash
curl http://localhost:8000/variant/1-55039447-G-T?dataset=gnomad_r4
```

### Via Python Client
```python
import httpx

# REST API
async with httpx.AsyncClient() as client:
    response = await client.get(
        "http://localhost:8000/variant/1-55039447-G-T",
        params={"dataset": "gnomad_r4"}
    )
    data = response.json()

# MCP endpoint (if using MCP client library)
async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_variant_allele_frequency",
                "arguments": {
                    "variant_id": "1-55039447-G-T",
                    "dataset": "gnomad_r4"
                }
            },
            "id": 1
        }
    )
```

## Troubleshooting

**"How do I know if the server is running?"**
- Check http://localhost:8000/health
- Look for "Starting gnomAD Unified Server..." in the logs

**"Can I run both interfaces separately?"**
- No, the unified server design means both interfaces run together
- This ensures they share the same cache and state

**"What if I need different ports?"**
- Change the port when starting: `uvicorn server:app --port 8080`
- Update your Claude Desktop config accordingly

**"How do I monitor performance?"**
- Check cache stats: http://localhost:8000/cache/stats
- Both interfaces share the same cache for optimal performance

## Benefits of the Unified Architecture

1. **Single Process**: Easier to deploy and monitor
2. **Shared Cache**: Both REST and MCP benefit from the same LRU cache
3. **Consistent State**: No synchronization issues between interfaces
4. **Unified Configuration**: One set of environment variables
5. **Simplified Operations**: One log stream, one process to manage