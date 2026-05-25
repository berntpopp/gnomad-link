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

The server provides:

- MCP Streamable HTTP at `http://127.0.0.1:8000/mcp`
- Health check at `http://127.0.0.1:8000/health`

## Claude HTTP

```bash
claude mcp add --transport http gnomad-link http://127.0.0.1:8000/mcp
```

For the default Docker Compose stack, use the host port mapped by
`GNOMAD_LINK_HOST_PORT`:

```bash
claude mcp add --transport http gnomad-link http://127.0.0.1:8020/mcp
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
| `get_variant_details` | Full variant annotation |
| `get_gene_details` | Gene constraint metrics |
| `get_gene_variants` | Variants in a gene with filtering |
| `get_transcript_details` | Transcript-level annotation |
| `search_genes` | Search genes by symbol or Ensembl ID |
| `resolve_variant_id` | Resolve variant IDs and rsIDs (preferred) |
| `search_variants` | Deprecated alias for `resolve_variant_id`; will be removed in one release |
| `get_clinvar_variant_details` | ClinVar clinical significance for a variant |
| `get_clinvar_meta` | ClinVar release metadata |
| `get_structural_variant` | Structural variant records |
| `get_mitochondrial_variant` | Mitochondrial variant records |
| `get_region` | Genomic region query |
| `liftover_variant` | Coordinate conversion GRCh37 <-> GRCh38 |
| `get_server_capabilities` | Server capabilities and tool metadata |

Note: `search_variants` is a deprecated alias for `resolve_variant_id`. Use
`resolve_variant_id` for new work. The alias will be removed in one release.

## Troubleshooting

- Confirm the server is running with `make mcp-serve-http`.
- Confirm the MCP endpoint is reachable: `curl http://127.0.0.1:8000/health`.
- Confirm the MCP endpoint is `http://127.0.0.1:8000/mcp`.
- If a client cannot use HTTP MCP, use the stdio fallback command.
- If tools are missing after an update, refresh the client's MCP/tool cache and
  reconnect.
