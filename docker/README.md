# Docker

## Quick Start

```bash
make docker-build
make docker-up
curl http://localhost:8020/health
make docker-down
```

The base Compose stack serves REST and MCP over HTTP:

- REST docs: `http://localhost:8020/docs`
- Health check: `http://localhost:8020/health`
- MCP endpoint: `http://localhost:8020/mcp`

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
# Edit GNOMAD_LINK_HOST_PORT, CORS_ORIGINS, and NPM_NETWORK_NAME for your host.
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

### Fleet Deploy Contract

`docker-compose.npm.yml` is the file the GeneFoundry fleet controller
(`strato_v6_docker_npm`) renders and deploys — it never builds from source. The
`gnomad-link` service there declares `user: "10001:10001"`, this image's own
uid:gid from `docker/Dockerfile`, because the controller's runtime observer
proves the effective uid from `/proc` and refuses a service with no numeric
`user`. The release Compose files named in `container-release.json`
(`docker-compose.yml`, `docker-compose.prod.yml`) must NOT declare `user`; the
shared release gate forbids it there. `tests/unit/docker/test_docker_compose.py`
guards both invariants.

To self-check a rendered Compose stack against the controller's own projection
logic before deploying (run from a checkout of `strato_v6_docker_npm`):

```bash
docker compose -f docker/docker-compose.yml -f docker/docker-compose.prod.yml \
  -f docker/docker-compose.npm.yml config --format json > /tmp/gnomad-link-rendered.json
uv run python -c "
import sys, json; sys.path.insert(0, 'scripts')
from utils.deployment_preflight import canonical_projection
p = canonical_projection(json.load(open('/tmp/gnomad-link-rendered.json')), project='gnomad-link')
for n, s in p['services'].items(): print(n, 'user=', s.get('user'))
print('PROJECTION OK')"
```

## Environment

Notable variables:

- `GNOMAD_API_URL` - upstream gnomAD GraphQL API.
- `GNOMAD_LINK_HOST_PORT` - host port for the base Compose stack, default `8020`.
- `MCP_PORT` - internal application port, default `8000`.
- `MCP_PATH` - hosted MCP path, default `/mcp`.
- `MCP_ALLOWED_HOSTS` - JSON list of exact request Host values; production must include
  `gnomad-link.genefoundry.org`.
- `MCP_ALLOWED_ORIGINS` - JSON list of browser origins accepted by the request guard.
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
