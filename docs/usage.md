# Usage Guide

## Quick Start

```bash
git clone <repository-url>
cd gnomad-link
uv sync --group dev
make mcp-serve-http
```

The server exposes:

- MCP Streamable HTTP: `http://127.0.0.1:8000/mcp`
- Health: `http://127.0.0.1:8000/health`

## Transport Modes

### Unified Mode (Recommended)

Single process; FastAPI `/health` host with FastMCP at `/mcp`.

```bash
make mcp-serve-http
```

Manual equivalent:

```bash
uv run python server.py --transport unified --host 127.0.0.1 --port 8000
```

### stdio Fallback

Use only for local clients that cannot connect to HTTP MCP endpoints.

```bash
make mcp-serve
```

## MCP Clients

### Claude Code HTTP

```bash
make mcp-serve-http
claude mcp add --transport http gnomad-link http://127.0.0.1:8000/mcp
```

When using the default Docker Compose stack:

```bash
claude mcp add --transport http gnomad-link http://127.0.0.1:8020/mcp
```

### Claude Desktop HTTP Config

```json
{
  "mcpServers": {
    "gnomad-link": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

### stdio Fallback Config

```json
{
  "mcpServers": {
    "gnomad-link-stdio": {
      "command": "gnomad-link-mcp",
      "env": {
        "PYTHONUNBUFFERED": "1",
        "LOG_LEVEL": "WARNING"
      }
    }
  }
}
```

## MCP Tool Examples

### List Available Tools

```bash
curl -sS http://127.0.0.1:8000/mcp \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

### Query Variant Frequencies

```bash
curl -sS http://127.0.0.1:8000/mcp \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_variant_frequencies","arguments":{"variant_id":"1-55039447-G-T","dataset":"gnomad_r4"}}}'
```

### Search Genes

```bash
curl -sS http://127.0.0.1:8000/mcp \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"search_genes","arguments":{"query":"BRCA2","reference_genome":"GRCh38"}}}'
```

### Get ClinVar Annotation

```bash
curl -sS http://127.0.0.1:8000/mcp \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"get_clinvar_variant_details","arguments":{"variant_id":"7-117559590-ATCT-A","reference_genome":"GRCh38"}}}'
```

### Liftover

```bash
curl -sS http://127.0.0.1:8000/mcp \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"liftover_variant","arguments":{"source_variant_id":"17-7577121-G-A","reference_genome":"GRCh37"}}}'
```

## Health Check

```bash
curl http://127.0.0.1:8000/health
```

## Configuration

Environment variables:

```bash
MCP_TRANSPORT=unified
MCP_HOST=127.0.0.1
MCP_PORT=8000
MCP_PATH=/mcp
GNOMAD_API_URL=https://gnomad.broadinstitute.org/api
CACHE_SIZE=1024
CACHE_TTL_MINUTES=60
LOG_LEVEL=INFO
```

Copy `.env.example` to `.env` for local overrides.

## Cache Management

Cache stats and clear are available via the CLI (not via MCP):

```bash
gnomad-link cache stats
gnomad-link cache clear
```

## Production Notes

- Prefer Streamable HTTP MCP behind HTTPS.
- Protect public deployments with OAuth or an authenticated reverse proxy.
- Keep MCP tools research-use scoped.
- Do not expose destructive cache operations through public MCP tools.
- Treat live gnomAD rate limits as upstream state, not local test failures.

See [docker/README.md](../docker/README.md) for Docker production deployment.
