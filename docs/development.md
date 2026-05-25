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
  for `gnomad_link/`, `server.py`, and `mcp_server.py`.
- Keep deterministic tests in `tests/unit/` and live upstream tests in
  `tests/integration/`.
- Preserve public REST paths, MCP tool names, and response schemas unless a task
  explicitly calls for a breaking change.

## Running Servers

```bash
make dev             # REST + MCP Streamable HTTP on 127.0.0.1:8000
make mcp-serve-http  # same hosted MCP endpoint
make mcp-serve       # stdio fallback for local clients
```

Manual equivalents:

```bash
uv run python server.py --transport unified --host 127.0.0.1 --port 8000
uv run python server.py --transport http --host 127.0.0.1 --port 8000
uv run python mcp_server.py
```

## MCP Development

Streamable HTTP at `/mcp` is the primary MCP transport.

```bash
make mcp-serve-http
claude mcp add --transport http gnomad-link http://127.0.0.1:8000/mcp
```

Use stdio only as a fallback for local clients that cannot connect to HTTP MCP:

```bash
make mcp-serve
```

Public MCP tools must remain research-use scoped and must not expose destructive
cache operations.

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
├── api/                    # GraphQL client and FastAPI routes
├── graphql/                # Query loader, builder, and query documents
├── models/                 # Pydantic response models and enums
├── services/               # Service layer and cache-aware data access
├── transports/             # Transport abstractions
├── cli.py                  # Command-line parser and helper commands
├── config.py               # Settings and server config
├── logging_config.py       # Logging setup
└── server_manager.py       # Unified REST/MCP lifecycle management
```

## Agentic Work

- Follow `AGENTS.md`.
- For multi-step work, update specs under `docs/superpowers/specs/` and plans
  under `docs/superpowers/plans/`.
- Keep edits scoped and commit coherent changes after `make ci-local` passes.
