# Claude And MCP Configuration

gnomAD Link exposes MCP over Streamable HTTP at `/mcp` when the unified server
is running. Use HTTP MCP for Claude Code, Claude Desktop versions with HTTP MCP
support, ChatGPT developer mode, and hosted MCP clients.

## Start The Server

```bash
make dev
```

The server provides:

- MCP Streamable HTTP at `http://127.0.0.1:8000/mcp`
- Health check at `http://127.0.0.1:8000/health`

## Claude Code HTTP

```bash
claude mcp add --transport http gnomad-link http://127.0.0.1:8000/mcp
```

For the default Docker Compose stack, use the non-conflicting host port:

```bash
claude mcp add --transport http gnomad-link http://127.0.0.1:8020/mcp
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

## Available Tools

- `get_variant_frequencies`, `get_variant_details`
- `get_gene_details`, `get_gene_variants`
- `get_transcript_details`
- `search_genes`, `resolve_variant_id`
- `search_variants` (deprecated alias for `resolve_variant_id`)
- `get_clinvar_variant_details`, `get_clinvar_meta`
- `get_structural_variant`, `get_mitochondrial_variant`
- `get_region`, `compute_variant_liftover`
- `get_server_capabilities`

Treat gnomAD results as research data. Do not use this server for diagnosis,
treatment, triage, patient management, or clinical decision support.
