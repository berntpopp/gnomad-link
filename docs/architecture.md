# Architecture Overview

## System Architecture

gnomAD Link is an MCP-first server that bridges the gnomAD (Genome Aggregation
Database) to AI applications. FastAPI is a thin host providing `/health` only
and mounting the FastMCP HTTP app at `/mcp`. All domain functionality is exposed
via MCP.

### Architecture Overview

```
     Clients (Claude Code, Claude Desktop, ChatGPT, curl)
                          |
           FastAPI /health host  (port 8020 Docker / 8000 dev)
                          |
               FastMCP HTTP app at /mcp
                          |
     +-----------+------------------+-------------------+
     |           |                  |                   |
  Variants    Genes/Transcripts   ClinVar    Specialty/Search
  tools        tools               tools      tools
     |           |                  |                   |
     +-----------+------------------+-------------------+
                          |
               gnomad_link/services/
               (FrequencyService, GraphQLClient, CacheManager)
                          |
               gnomAD GraphQL API (v2, v3, v4)
```

## Core Components

### 1. FastAPI /health Host

- **Purpose**: Minimal HTTP host for the MCP app; provides `/health` only.
- **Mount**: FastMCP HTTP app at `/mcp` via `app.mount("/mcp", mcp.http_app())`.
- **No REST routes**: `/docs`, `/redoc`, `/openapi.json`, and all `/variant`,
  `/gene`, `/clinvar`, etc. routes are removed.

### 2. MCP Facade (`gnomad_link/mcp/`)

The hand-authored MCP facade is the primary interface:

```
gnomad_link/mcp/
  facade.py       - create_gnomad_mcp() entry point, server instructions
  tools/
    variants.py   - get_variant_frequencies, get_variant_details
    genes.py      - get_gene_details, get_gene_variants
    clinvar.py    - get_clinvar_variant_details, get_clinvar_meta
    coordinates.py - compute_variant_liftover, get_region
    specialty.py  - get_structural_variant, get_mitochondrial_variant,
                    get_transcript_details
    search.py     - search_genes, resolve_variant_id, search_variants
    metadata.py   - get_server_capabilities
  resources.py    - gnomad://capabilities, gnomad://usage
  errors.py       - structured error envelopes
```

Every tool is explicitly registered with:

- LLM-oriented description starting with "Use this when..."
- Concrete input constraints via `Annotated` and `pydantic.Field`
- `ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True,
  openWorldHint=True)` for gnomAD API-backed tools

### 3. Unified Server Manager

`UnifiedServerManager` orchestrates the system:

```python
class UnifiedServerManager:
    async def create_fastapi_app(self) -> FastAPI:
        """Create FastAPI app with /health and mounted MCP."""

    async def start_unified_server(self, config: ServerConfig): ...
```

In unified HTTP mode, REST and MCP share one `FrequencyService` instance,
cache, and GraphQL client.

### 4. Business Logic Layer

#### FrequencyService

- Core business logic for all variant and gene queries
- Async-LRU caching with configurable size and TTL
- Shared across all transport interfaces

#### GraphQLClient (UnifiedGnomadClient)

- Version-aware GraphQL communication with gnomAD API
- Automatic version routing (v2/v3/v4), timeout handling, connection pooling

#### CacheManager

- Centralized caching; single instance across all transports
- Cache stats and clear via `gnomad-link cache` CLI subcommands

### 5. Data Layer

- **Queries**: Version-specific GraphQL documents under
  `gnomad_link/graphql/queries/` (`v2/`, `v3/`, `v4/`, `common/`)
- **Datasets**: `gnomad_r2_1` on GRCh37; `gnomad_r3` and `gnomad_r4` on
  GRCh38; `gnomad_r4` is the default

## Transport Selection

### Unified (Recommended)

```bash
make dev
# or
uv run gnomad-link serve --transport unified --host 127.0.0.1 --port 8000
```

Single process. FastAPI host at root with MCP at `/mcp`. Health check at
`/health`.

## Configuration

### ServerConfig

```python
@dataclass
class ServerConfig:
    transport: Literal["unified", "http"] = "unified"
    host: str = "127.0.0.1"
    port: int = 8000
    mcp_path: str = "/mcp"
    log_level: str = "INFO"
```

### Environment Variables

```bash
MCP_TRANSPORT=unified
MCP_HOST=127.0.0.1
MCP_PORT=8000
MCP_PATH=/mcp

LOG_LEVEL=INFO
LOG_FORMAT=json

GNOMAD_API_URL=https://gnomad.broadinstitute.org/api
CACHE_SIZE=1024
CACHE_TTL_MINUTES=60
```

## Error Handling

MCP tools return structured error envelopes:

```json
{
  "error": {
    "code": "upstream_error",
    "message": "gnomAD API returned an error",
    "details": {...}
  }
}
```

## Security

- Input validation via Pydantic models throughout
- No sensitive data in error responses
- Destructive cache operations are CLI-only; not exposed via MCP
- Production deployments should use HTTPS and an authenticated reverse proxy

## Deployment

### Docker

```bash
cp .env.docker.example .env.docker
make docker-build
make docker-up
curl http://localhost:8020/health
```

See [docker/README.md](../docker/README.md) for production and Nginx Proxy
Manager overlays.

### Health Check

```bash
curl http://localhost:8020/health
```

### Cache Management (CLI)

```bash
gnomad-link cache stats
gnomad-link cache clear
```
