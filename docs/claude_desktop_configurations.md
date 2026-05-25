# Claude And MCP Configuration

gnomAD Link exposes MCP over Streamable HTTP at `/mcp` when the unified server
is running. Use HTTP MCP for Claude Code, Claude Desktop versions with HTTP MCP
support, ChatGPT developer mode, and hosted MCP clients.

## Start The Server

```bash
make mcp-serve-http
```

The unified server provides:

- REST API at `http://127.0.0.1:8000/`
- Interactive docs at `http://127.0.0.1:8000/docs`
- MCP Streamable HTTP at `http://127.0.0.1:8000/mcp`

## Claude Code HTTP

```bash
claude mcp add --transport http gnomad-link http://127.0.0.1:8000/mcp
```

For hosted deployments, use your public HTTPS endpoint:

```bash
claude mcp add --transport http gnomad-link https://your-domain.example/mcp
```

## Claude Desktop HTTP Config

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

## ChatGPT Developer Mode

Add a remote MCP connector with this URL:

```text
https://your-domain.example/mcp
```

Use no authentication only for local or private deployments. Public deployments
should be protected by OAuth or an authenticated reverse proxy.

## stdio Fallback

Use stdio only for local desktop workflows that cannot connect to HTTP MCP
endpoints:

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

## Available Tools

- `get_variant_frequencies`
- `search_genes`
- `search_transcripts`
- `get_structural_variants`
- `search_clinvar_variants`
- `get_clinvar_variant_details`

Treat gnomAD results as research data. Do not use this server for diagnosis,
treatment, triage, patient management, or clinical decision support.
