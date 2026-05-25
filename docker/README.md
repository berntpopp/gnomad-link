# Docker

## Quick Start

```bash
make docker-build
make docker-up
curl http://localhost:8000/health
make docker-down
```

The base Compose stack serves REST and MCP over HTTP:

- REST docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`
- MCP endpoint: `http://localhost:8000/mcp`

## Compose Overlays

- `docker-compose.yml` - base service.
- `docker-compose.dev.yml` - bind-mounted source for containerized development.
- `docker-compose.prod.yml` - production hardening with read-only filesystem,
  dropped capabilities, resource limits, and service-level health checks.
- `docker-compose.npm.yml` - Nginx Proxy Manager exposure without publishing
  host ports.

Layer overlays explicitly:

```bash
docker compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up --build
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml up -d --build
```

## Production/NPM Deployment

Use `.env.docker` for Docker-specific production settings:

```bash
cp .env.docker.example .env.docker
# Edit MCP_PORT, CORS_ORIGINS, and NPM_NETWORK_NAME for your host.
docker compose \
  --env-file .env.docker \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.prod.yml \
  -f docker/docker-compose.npm.yml \
  up -d --build
```

The NPM overlay attaches `gnomad-link` to both the private Compose network and
the external NPM network. In Nginx Proxy Manager, proxy to:

- Forward hostname: `gnomad-link`
- Forward port: `8000`
- Scheme: `http`

The public MCP endpoint is then available at `https://your-domain.example/mcp`.

## Environment

Notable variables:

- `GNOMAD_API_URL` - upstream gnomAD GraphQL API.
- `MCP_PORT` - host port for the base Compose stack, default `8000`.
- `MCP_PATH` - hosted MCP path, default `/mcp`.
- `CORS_ORIGINS` - comma-separated allowed origins or `*`.
- `CACHE_SIZE` and `CACHE_TTL_MINUTES` - in-memory cache controls.
- `NPM_NETWORK_NAME` - external Docker network used by Nginx Proxy Manager.

## Validation

```bash
make docker-prod-config
make docker-npm-config
docker build -f docker/Dockerfile -t gnomad-link:local .
```

The image runs as a non-root user and does not define an image-level
`HEALTHCHECK`; Compose owns service health checks so one-off container commands
can reuse the image without inheriting an HTTP probe.
