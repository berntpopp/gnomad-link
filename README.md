# gnomAD Link

MCP server for gnomAD population-genetics data. FastAPI is a thin host
providing `/health` only; all domain functionality is exposed via MCP.

## Core Purpose

Programmatic access to human genetic variation data from gnomAD, the world's
largest public database of human genetic variants. Enables:

- **AI Assistants**: Access gnomAD data through native MCP tool interfaces
- **Researchers**: Query variant frequencies, genes, ClinVar, structural
  variants, mitochondrial variants, and liftover data
- **Developers**: Build applications using standardized genetic variant data

## Key Features

- **MCP-First Architecture**: Hand-authored FastMCP facade over the gnomAD
  service layer
- **22 MCP Tools**: Variants, genes, transcripts, ClinVar, structural variants,
  mitochondrial variants, liftover, region, coverage, carrier frequency,
  cross-dataset comparison, diagnostics, and capabilities
- **Transport**: Streamable HTTP only (unified FastAPI host + mounted MCP)
- **Comprehensive Data**: Allele frequencies across 8 global populations
- **High Performance**: Async operations with intelligent caching
- **Type Safety**: Full Pydantic v2 validation
- **Production Ready**: Docker Compose, health checks, error envelopes

## Quick Start

### Installation

```bash
git clone <repository-url>
cd gnomad-link
uv sync --group dev
```

### Start The Server

```bash
make dev
```

The server listens on `http://127.0.0.1:8020/mcp` (Docker default port).
For local dev without Docker:

```bash
uv run gnomad-link serve --transport unified --host 127.0.0.1 --port 8000
```

### Connect Claude Code

```bash
claude mcp add --transport http gnomad-link http://127.0.0.1:8020/mcp
```

Local dev (non-Docker):

```bash
claude mcp add --transport http gnomad-link http://127.0.0.1:8000/mcp
```

### Verify The MCP Endpoint

```bash
curl -sS http://127.0.0.1:8020/mcp \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## Configuration

### Environment Variables

```env
MCP_TRANSPORT=unified
MCP_HOST=127.0.0.1
MCP_PORT=8000
MCP_PATH=/mcp

GNOMAD_API_URL=https://gnomad.broadinstitute.org/api
CACHE_SIZE=1024
CACHE_TTL_MINUTES=60

LOG_LEVEL=INFO
LOG_FORMAT=json   # json (prod) or console (dev)
```

Copy `.env.example` to `.env` for local overrides.
Copy `.env.docker.example` to `.env.docker` for Docker overrides.

## MCP Integration

### Claude Code (HTTP)

```bash
make dev
claude mcp add --transport http gnomad-link http://127.0.0.1:8000/mcp
```

Docker Compose stack (uses host port `GNOMAD_LINK_HOST_PORT`, default 8020):

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

## Available MCP Tools

| Tool | Purpose |
|------|---------|
| `get_server_capabilities` | Server capabilities and tool metadata |
| `get_variant_frequencies` | Allele counts and frequencies for a variant |
| `get_variant_details` | Full variant annotation |
| `compare_variant_across_datasets` | Compare one variant's AF across gnomAD releases (r4/r3/r2_1) |
| `get_gene_details` | Gene constraint metrics (pLI/oe_lof) |
| `get_gene_variants` | Variants in a gene with filtering |
| `get_gene_summary` | Gene-level constraint + variant/ClinVar summary |
| `get_clinvar_variant_details` | ClinVar clinical significance |
| `get_clinvar_meta` | ClinVar release metadata (deprecated; use `get_server_capabilities`) |
| `compute_variant_liftover` | Coordinate conversion GRCh37 <-> GRCh38 |
| `get_structural_variant` | Structural variant record |
| `search_structural_variants` | Find structural variants by gene or region |
| `get_mitochondrial_variant` | Mitochondrial variant record |
| `get_region` | Genes and ClinVar variants in a genomic region |
| `get_coverage` | Coverage statistics over a region |
| `get_transcript_details` | Transcript-level annotation with optional GTEx expression |
| `search_genes` | Search genes by symbol or Ensembl ID |
| `resolve_variant_id` | Resolve rsIDs or loose text to canonical variant IDs |
| `search_variants` | Deprecated alias for `resolve_variant_id` |
| `compute_carrier_frequency` | Single-variant carrier frequency (AR/XL) |
| `compute_gene_carrier_frequency` | Gene-level recessive carrier rate |
| `get_diagnostics` | Recent errors, schema drift, and health status |

**Federation:** leaf tool names are intentionally unprefixed per the GeneFoundry
Tool-Naming Standard v1. The canonical gateway **namespace token** is `gnomad`;
when federated behind `genefoundry-router`, tools surface as `gnomad_<tool>`
(e.g. `gnomad_get_variant_frequencies`, `gnomad_get_diagnostics`). The MCP server
identity (`serverInfo.name`) is `gnomad-link`.

## Architecture

```
     Clients (Claude Code, Claude Desktop, ChatGPT, curl)
                          |
             FastAPI /health host  (port 8020)
                          |
               FastMCP HTTP app at /mcp
                          |
     +-----------+------------------+-------------------+
     |           |                  |                   |
  Variants    Genes/Transcripts   ClinVar    Specialty/Search
     |           |                  |                   |
     +-----------+------------------+-------------------+
                          |
               gnomad_link/services/
                          |
               gnomAD GraphQL API (v2, v3, v4)
```

## Understanding gnomAD

gnomAD aggregates genetic data from hundreds of thousands of individuals to
provide:

- **Population Frequencies**: How common variants are across different ancestries
- **Constraint Metrics**: How tolerant genes are to mutations
- **Clinical Annotations**: Disease associations from ClinVar
- **Quality Metrics**: Sequencing depth and quality scores

### Datasets

- `gnomad_r2_1`: GRCh37, exome data with 125k+ individuals
- `gnomad_r3`: GRCh38, genome data with 76k+ individuals
- `gnomad_r4`: GRCh38, latest release with 730k+ individuals (default)

### Useful Resources

- [gnomAD Browser](https://gnomad.broadinstitute.org/)
- [gnomAD API Documentation](https://gnomad.broadinstitute.org/api)
- [GA4GH Standards Integration](https://gnomad.broadinstitute.org/news/2023-11-ga4gh-gks/)

## Development

```bash
make install       # Install dependencies
make test          # Run unit tests
make test-cov      # Run with coverage
make lint          # Lint with Ruff
make format        # Format with Ruff
make typecheck     # Type check with mypy
make ci-local      # Full local CI gate
```

```bash
make dev           # Start dev server (console logs)
make run-prod      # Start production server (JSON logs)
```

## Docker Deployment

```bash
cp .env.docker.example .env.docker
make docker-build
make docker-up
curl http://localhost:8020/health
```

For production or Nginx Proxy Manager deployment details, see
[docker/README.md](docker/README.md).

## Documentation

- [Architecture Guide](docs/architecture.md)
- [Usage Guide](docs/usage.md)
- [MCP Connection Guide](docs/MCP_CONNECTION_GUIDE.md)
- [Development Guide](docs/development.md)
- [gnomAD GraphQL Reference](docs/gnomad_graphql/)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Follow guidelines in [docs/development.md](docs/development.md)
4. Run `make ci-local`
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file

## Acknowledgments

- **[gnomAD](https://gnomad.broadinstitute.org/)** - Genome Aggregation Database
- **[Broad Institute](https://www.broadinstitute.org/)** - gnomAD maintainers
- **[FastAPI](https://fastapi.tiangolo.com/)** - Web framework host
- **[FastMCP](https://github.com/jlowin/fastmcp)** - MCP implementation
- **[Claude AI](https://claude.ai/)** - MCP protocol development

## Citation

If using this tool in research, please cite:

**gnomAD Database:**
```
Karczewski, K.J., Francioli, L.C., Tiao, G. et al.
The mutational constraint spectrum quantified from variation in 141,456 humans.
Nature 581, 434-443 (2020).
```

**gnomAD v4:**
```
Chen, S., Francioli, L.C., Goodrich, J.K. et al.
A genomic mutational constraint map using variation in 76,156 human genomes.
Nature 625, 92-100 (2024).
```

---

**Research use only. Not for clinical decision support.**
