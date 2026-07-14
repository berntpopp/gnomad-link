# Configuration

Every setting is an environment variable read by `gnomad_link/config.py`
(`Settings`, a `pydantic-settings` model). Copy `.env.example` to `.env` for local
overrides, and `.env.docker.example` to `.env.docker` for Docker/NPM deployments.

No API key or token is required: the gnomAD GraphQL API is public and
unauthenticated.

## Upstream

| Variable | Default | Notes |
|----------|---------|-------|
| `GNOMAD_API_URL` | `https://gnomad.broadinstitute.org/api` | gnomAD GraphQL endpoint. No auth. |
| `GNOMAD_MAX_CONCURRENCY` | `5` | Max in-flight upstream GraphQL requests. Bounds burst pressure on gnomAD's rate limiter; a jittered retry layer absorbs residual 429s. Keep it conservative against the public endpoint. |
| `GNOMAD_REQUEST_TIMEOUT` | `60` | Per-request upstream timeout, in seconds. Large-gene payloads (CFTR is ~13 MB) complete in ~5-6 s, but cold responses need headroom — too tight a timeout trips the retry layer and multiplies wall-clock time. |
| `GNOMAD_QUEUE_WAIT_TIMEOUT` | `20` | Max seconds a request waits for a concurrency slot before returning fast, retryable `rate_limited` backpressure instead of queuing until the caller's own tool-call timeout fires. |

## Cache

The server holds no local database; it is a live proxy with an in-memory cache.

| Variable | Default | Notes |
|----------|---------|-------|
| `CACHE_SIZE` | `1024` | Max cached entries. |
| `CACHE_TTL_MINUTES` | `60` | Entry time-to-live. |

Cache inspection and clearing are **CLI-only** and deliberately not exposed as MCP
tools:

```bash
gnomad-link cache stats
gnomad-link cache clear
```

## Transport

Streamable HTTP only. There is no SSE and no stdio entry point.

| Variable | Default | Notes |
|----------|---------|-------|
| `MCP_TRANSPORT` | `unified` | `unified` (FastAPI `/health` host + mounted MCP at `/mcp`) or `http`. |
| `MCP_HOST` | `127.0.0.1` | Bind address. |
| `MCP_PORT` | `8000` | Application port inside the process/container. |
| `MCP_PATH` | `/mcp` | MCP mount path; a leading `/` is added if missing. |

Port topology, which differs between the two ways of running the server:

- Local (non-Docker) dev listens on **8000** — `http://127.0.0.1:8000/mcp`.
- The Docker Compose stack publishes container port 8000 on host port
  **`GNOMAD_LINK_HOST_PORT`, default 8020** — `http://127.0.0.1:8020/mcp`.

## Request boundary (Host / Origin)

Every HTTP route is gated by exact Host and Origin allowlists. Both are
**JSON-encoded lists** in the environment, not comma-separated strings.

| Variable | Default | Notes |
|----------|---------|-------|
| `MCP_ALLOWED_HOSTS` | `["localhost","127.0.0.1","::1"]` | Exact request `Host` values. **Wildcards (`*`, `?`, `[`, `]`) are rejected at startup** by a validator. A production deployment must add its public reverse-proxy hostname, e.g. `gnomad-link.genefoundry.org`. |
| `MCP_ALLOWED_ORIGINS` | `[]` | Browser `Origin` values accepted by the request guard. Empty still admits non-browser clients, which send no `Origin`. |
| `CORS_ORIGINS` | `*` | Comma-separated list (or `*`) controlling CORS *response* headers. Distinct from `MCP_ALLOWED_ORIGINS`, which is the request-admission gate. |

```env
MCP_ALLOWED_HOSTS='["localhost","127.0.0.1","::1","gnomad-link.genefoundry.org"]'
MCP_ALLOWED_ORIGINS='[]'
```

The server is unauthenticated by design: it is meant to sit behind the
`genefoundry-router` or an authenticated reverse proxy, which owns edge auth. Do
not publish it directly.

## Logging and operations

| Variable | Default | Notes |
|----------|---------|-------|
| `LOG_LEVEL` | `INFO` | |
| `LOG_FORMAT` | `json` | `json` in production, `console` in dev (structlog renderer). |
| `ENABLE_SWAGGER` | `true` | |
| `ENABLE_MONITORING` | `true` | |
| `GRACEFUL_SHUTDOWN_TIMEOUT` | `30` | Seconds. |
| `MAX_PAGE_SIZE` | `100` | |

## Docker-only

| Variable | Default | Notes |
|----------|---------|-------|
| `GNOMAD_LINK_HOST_PORT` | `8020` | Host port published by the base Compose stack. |
| `NPM_NETWORK_NAME` | `npm_default` | External Docker network the Nginx Proxy Manager container is attached to. |
| `GNOMAD_LINK_IMAGE` | — | Digest-pinned image reference. The production overlay refuses to render without it. |

See [docker/README.md](../docker/README.md) for the deployment procedure and the
Compose overlays.
