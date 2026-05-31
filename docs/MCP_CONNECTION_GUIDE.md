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

## Gemini (hosted MCP)

Gemini's remote-MCP support is **Streamable HTTP only** (not SSE). Point the
client at the `/mcp` endpoint.

### Naming constraint

Hosted-MCP server names must be `snake_case` -- hyphens are not allowed.
Use `gnomad_link` (not `gnomad-link`):

```yaml
# Example Gemini hosted-MCP config fragment
mcpServers:
  - name: "gnomad_link"
    url: "https://your-domain.example/mcp"
    transport: "streamable_http"
```

For local dev replace the URL with `http://127.0.0.1:8000/mcp` or
`http://127.0.0.1:8020/mcp` (Docker).

### Tool-set guidance

Gemini function-calling guidance recommends keeping the active tool set to
roughly 10-20 tools. This server exposes 22 tools. Use an `allowed_tools` list
to select a focused subset for your workflow:

```yaml
mcpServers:
  - name: "gnomad_link"
    url: "https://your-domain.example/mcp"
    transport: "streamable_http"
    allowed_tools:
      - get_server_capabilities
      - resolve_variant_id
      - get_variant_frequencies
      - get_variant_details
      - search_genes
      - get_gene_details
      - get_clinvar_variant_details
      - liftover_variant
      - compare_variant_across_datasets
      - compute_gene_carrier_frequency
      - get_region
      - get_gnomad_diagnostics
```

The 22 tools fall into these categories:

| Category | Tools |
|----------|-------|
| variant | `get_variant_frequencies`, `get_variant_details`, `compare_variant_across_datasets`, `get_mitochondrial_variant`, `get_structural_variant`, `search_structural_variants`, `compute_carrier_frequency` |
| gene | `get_gene_details`, `get_gene_variants`, `get_gene_summary`, `compute_gene_carrier_frequency`, `search_genes` |
| clinvar | `get_clinvar_variant_details`, `get_clinvar_meta` |
| coordinates | `liftover_variant`, `get_region`, `get_transcript_details`, `get_coverage` |
| carrier | `compute_carrier_frequency`, `compute_gene_carrier_frequency` |
| search | `search_genes`, `resolve_variant_id`, `search_variants`, `search_structural_variants` |
| metadata | `get_server_capabilities`, `get_gnomad_diagnostics` |

If the Gemini client cannot restrict tools at connection time, clients that
support deferred tool loading or client-side tool search can load only the
tools relevant to the current task, keeping the effective active set within
the 10-20 recommendation.

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

22 tools across seven categories.

| Tool | Use When |
|------|----------|
| `get_server_capabilities` | Discover server capabilities and tool metadata |
| `get_variant_frequencies` | Query allele counts and frequencies for a variant |
| `get_variant_details` | Full variant annotation |
| `compare_variant_across_datasets` | Compare one variant's AF across gnomAD releases (r4/r3/r2_1) |
| `get_gene_details` | Gene constraint metrics (pLI/oe_lof) |
| `get_gene_variants` | Variants in a gene with filtering |
| `get_gene_summary` | Gene-level constraint + variant/ClinVar summary |
| `get_clinvar_variant_details` | ClinVar clinical significance for a variant |
| `get_clinvar_meta` | ClinVar release metadata (deprecated; use `get_server_capabilities`) |
| `liftover_variant` | Coordinate conversion GRCh37 <-> GRCh38 |
| `get_structural_variant` | Structural variant record |
| `search_structural_variants` | Find structural variants by gene or region |
| `get_mitochondrial_variant` | Mitochondrial variant record |
| `get_region` | Genes and ClinVar variants in a genomic region |
| `get_coverage` | Coverage statistics over a region |
| `get_transcript_details` | Transcript-level annotation with optional GTEx expression |
| `search_genes` | Search genes by symbol or Ensembl ID |
| `resolve_variant_id` | Resolve rsIDs or loose text to canonical variant IDs (preferred) |
| `search_variants` | Deprecated alias for `resolve_variant_id`; will be removed in one release |
| `compute_carrier_frequency` | Single-variant carrier frequency (AR/XL) |
| `compute_gene_carrier_frequency` | Gene-level recessive carrier rate |
| `get_gnomad_diagnostics` | Recent errors, schema drift, and health status |

Note: `search_variants` and `get_clinvar_meta` are deprecated. Use
`resolve_variant_id` and `get_server_capabilities` for new work.

## Troubleshooting

- Confirm the server is running with `make mcp-serve-http`.
- Confirm the MCP endpoint is reachable: `curl http://127.0.0.1:8000/health`.
- Confirm the MCP endpoint is `http://127.0.0.1:8000/mcp`.
- If a client cannot use HTTP MCP, use the stdio fallback command.
- If tools are missing after an update, refresh the client's MCP/tool cache and
  reconnect.
