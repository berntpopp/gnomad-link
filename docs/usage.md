# Usage Guide

## Quick Start

```bash
git clone <repository-url>
cd gnomad-link
uv sync --group dev
uv run python server.py --transport unified
```

Access:

- REST docs: `http://127.0.0.1:8000/docs`
- MCP Streamable HTTP: `http://127.0.0.1:8000/mcp`
- Health: `http://127.0.0.1:8000/health`

## Transport Modes

### Unified Mode

Recommended for normal use. Runs REST and MCP Streamable HTTP in one process.

```bash
make mcp-serve-http
```

Manual equivalent:

```bash
uv run python server.py --transport unified --host 127.0.0.1 --port 8000
```

### HTTP-Only Mode

Runs the REST API without MCP.

```bash
uv run python server.py --transport http --host 127.0.0.1 --port 8000
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

## REST Examples

```bash
curl "http://127.0.0.1:8000/variant/1-55039447-G-T?dataset=gnomad_r4"
curl "http://127.0.0.1:8000/search/gene?query=BRCA2&reference_genome=GRCh38"
curl "http://127.0.0.1:8000/clinvar/variant/7-117559590-ATCT-A?reference_genome=GRCh38"
curl "http://127.0.0.1:8000/liftover/?source_variant_id=17-7577121-G-A&reference_genome=GRCh37"
```

## MCP Endpoint

The MCP endpoint is available at:

```text
http://127.0.0.1:8000/mcp
```

Use MCP clients rather than hand-written curl for normal tool calls. If you need
to debug connectivity, first confirm REST docs and health are reachable:

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

## Production Notes

- Prefer Streamable HTTP MCP behind HTTPS.
- Protect public deployments with OAuth or an authenticated reverse proxy.
- Keep MCP tools research-use scoped.
- Do not expose destructive cache operations through public MCP tools.
- Treat live gnomAD rate limits as upstream state, not local test failures.

Minimal container sketch:

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install uv && uv sync --frozen --no-dev

EXPOSE 8000
CMD ["uv", "run", "python", "server.py", "--transport", "unified", "--host", "0.0.0.0", "--port", "8000"]
```
