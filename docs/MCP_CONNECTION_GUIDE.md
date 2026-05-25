# MCP Server Connection Guide

gnomAD Link exposes a research-use MCP surface for gnomAD variant, gene,
transcript, region, ClinVar, structural variant, mitochondrial variant, and
liftover data.

| Mode | Endpoint | Status | Use Case |
|------|----------|--------|----------|
| Streamable HTTP | `/mcp` | Recommended | Claude HTTP, ChatGPT developer mode, hosted remote MCP clients |
| stdio | `gnomad-link-mcp` | Local fallback | Local desktop-only workflows |

The tools expose public gnomAD research data and must not be used for diagnosis,
treatment, triage, patient management, or clinical decision support.

## Start The Server

```bash
make mcp-serve-http
```

The unified server provides:

- REST API at `http://127.0.0.1:8000/`
- Interactive docs at `http://127.0.0.1:8000/docs`
- MCP Streamable HTTP at `http://127.0.0.1:8000/mcp`

## Claude HTTP

```bash
claude mcp add --transport http gnomad-link http://127.0.0.1:8000/mcp
```

For hosted deployments:

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

| Tool | Use When |
|------|----------|
| `get_variant_frequencies` | Query allele counts and frequencies for a variant |
| `search_genes` | Search genes by symbol or Ensembl ID |
| `search_transcripts` | Search transcript records |
| `get_structural_variants` | Query structural variant records |
| `search_clinvar_variants` | Search ClinVar-associated variants |
| `get_clinvar_variant_details` | Fetch ClinVar detail for a variant |

## Troubleshooting

- Confirm the server is running in unified mode with `make mcp-serve-http`.
- Confirm `http://127.0.0.1:8000/docs` loads in a browser.
- Confirm the MCP endpoint is `http://127.0.0.1:8000/mcp`.
- If a client cannot use HTTP MCP, use the stdio fallback command.
- If tools are missing after an update, refresh the client's MCP/tool cache and
  reconnect.
