# Development Guide

## Prerequisites

- Python 3.12+
- `uv`
- `make`

## Setup

```bash
git clone <repository-url>
cd gnomad-link
make install
```

`uv.lock` is the dependency lock source of truth. Update it with:

```bash
make lock
```

## Daily Workflow

```bash
make format          # Ruff formatter
make lint            # Ruff lint
make typecheck       # mypy
make test            # deterministic unit tests
make ci-local        # local CI-equivalent gate
```

Useful focused commands:

```bash
make test-fast
make test-unit
make test-integration
make test-cov
make lint-fix
make lint-loc
make precommit
make docker-build
make docker-up
make docker-prod-config
make docker-npm-config
```

`make test` and `make ci-local` run only deterministic unit tests from
`tests/unit/`. Use `make test-integration` only when intentionally validating
upstream gnomAD behavior. Live tests may fail when the upstream API rate-limits
requests.

## Code Quality

- Use Ruff for formatting and linting.
- Use mypy for type checking.
- Use modern Python typing such as `list[str]`, `dict[str, int]`, and
  `str | None`.
- Keep production Python files under 600 lines. `make lint-loc` enforces this
  for `gnomad_link/`.
- Keep deterministic tests in `tests/unit/` and live upstream tests in
  `tests/integration/`.
- Keep Docker config tests deterministic; do not require Docker Engine for
  `make test`.
- Preserve MCP tool names and response schemas unless a task explicitly calls
  for a breaking change. REST is intentionally minimal (`/health` only).

## Running Servers

```bash
make dev             # console logs, MCP HTTP server on 127.0.0.1:8000
make run-prod        # JSON logs, MCP HTTP server on 0.0.0.0:8000
```

Manual equivalent:

```bash
uv run gnomad-link serve --transport unified --host 127.0.0.1 --port 8000
```

## MCP Development

Streamable HTTP at `/mcp` is the primary MCP transport.

```bash
make dev
claude mcp add --transport http gnomad-link http://127.0.0.1:8000/mcp
```

Public MCP tools must remain research-use scoped and must not expose destructive
cache operations.

## Docker Development

Docker assets live under `docker/` and mirror the companion MCP repositories:

```text
docker/
├── Dockerfile
├── README.md
├── docker-compose.dev.yml
├── docker-compose.npm.yml
├── docker-compose.prod.yml
└── docker-compose.yml
```

Use the Makefile wrappers for common workflows:

```bash
make docker-build
make docker-up
make docker-logs
make docker-down
```

Validate production overlays without starting containers:

```bash
make docker-prod-config
make docker-npm-config
```

The Docker image serves the FastAPI `/health` host with FastMCP at `/mcp`.
Health checks are defined in Compose services, not in the image, so future
one-off container commands can reuse the image without inheriting an HTTP health
probe.

## Test Structure

```text
tests/
├── conftest.py
├── integration/
│   └── test_*_endpoints.py
└── unit/
    ├── test_base_client.py
    ├── test_cli.py
    ├── test_query_builder.py
    ├── test_query_loader.py
    └── test_services.py
```

Endpoint tests under `tests/integration/` call the live gnomAD API and are
marked `integration`. Unit tests should be deterministic and suitable for local
CI.

## Project Structure

```text
gnomad_link/
├── api/                    # GraphQL client (routes removed; /health only in gnomad_link/server_manager.py)
├── graphql/                # Query loader, builder, and query documents
├── mcp/                    # Hand-authored MCP facade (tools, resources, errors)
├── models/                 # Pydantic response models and enums
├── services/               # Service layer and cache-aware data access
├── transports/             # Transport abstractions
├── cli.py                  # Command-line parser and cache helper commands
├── config.py               # Settings and server config
├── logging_config.py       # Logging setup
└── server_manager.py       # Unified FastAPI+MCP lifecycle management
```

## Agentic Work

- Follow `AGENTS.md`.
- For multi-step work, update specs under `docs/superpowers/specs/` and plans
  under `docs/superpowers/plans/`.
- Keep edits scoped and commit coherent changes after `make ci-local` passes.
