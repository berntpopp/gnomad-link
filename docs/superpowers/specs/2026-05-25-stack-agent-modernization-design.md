# gnomAD Link Stack And Agent Modernization Design

## Context

`gnomad-link` is a Python FastAPI and MCP server for gnomAD GraphQL data. The
neighboring `pubtator-link` and `genereviews-link` repositories have moved to a
newer shared project shape:

- Python 3.12 baseline
- `uv` dependency and lock workflow
- `hatchling` builds
- Ruff formatting and linting
- mypy checks
- local CI through `make ci-local`
- shared agent instructions in `AGENTS.md`
- minimal Claude Code entrypoint in `CLAUDE.md`
- per-file line budget enforcement for LLM-friendly maintenance

`gnomad-link` still uses a Python 3.9 baseline, `setuptools`, direct `pip`
installation instructions, Black/isort/flake8 Makefile targets, and no shared
agent guidance.

## Goal

Modernize `gnomad-link` to match the sibling MCP repositories while preserving
runtime behavior and avoiding broad internal rewrites.

## Scope

In scope:

- Update packaging metadata to use `hatchling`, Python 3.12+, bounded modern
  dependencies, dependency groups, project scripts, and package build metadata.
- Replace the Makefile workflow with `uv`-first targets aligned with the sibling
  repositories.
- Add `AGENTS.md` and a minimal `CLAUDE.md` for multi-agent development with
  Claude Code, Codex, and other LLM coding tools.
- Add pre-commit configuration and file-size budget tooling.
- Add `uv.lock` by resolving the updated project metadata.
- Replace the CLI health check's undeclared `requests` dependency with `httpx`.
- Refresh README setup and development commands to point at `uv` and the modern
  Makefile workflow.

Out of scope:

- Rewriting route/service internals to match sibling module names.
- Changing public REST or MCP endpoint behavior.
- Adding Docker deployment files.
- Adding database, embedding, or corpus workflows from the other projects.

## Architecture

The runtime architecture stays the same:

- `server.py` remains the unified REST/MCP entrypoint.
- `mcp_server.py` remains the backwards-compatible stdio MCP entrypoint.
- `gnomad_link/` remains the Python package containing API routes, GraphQL
  clients, models, services, transports, and server management.

The development architecture changes:

- `pyproject.toml` becomes the package, dependency, test, lint, type-check, and
  coverage source of truth.
- `uv.lock` becomes the dependency lock source of truth.
- `Makefile` becomes the stable command interface for humans and agents.
- `AGENTS.md` becomes the shared repository instruction file.
- `CLAUDE.md` only references `AGENTS.md` and adds Claude-specific notes.
- `scripts/check_file_size.py` enforces the same 600-line Python module budget
  used in the sibling repos.

## Testing And Verification

Required checks:

- A focused regression test verifies `gnomad_link.cli.handle_health_command`
  uses mockable `httpx.get` behavior and no longer relies on undeclared
  `requests`.
- `make lint-loc` verifies the new line-budget tooling.
- `make test` verifies the existing test suite after dependency and CLI changes.
- `make ci-local` is the final intended local CI target. If it fails because
  older code is not yet strict-mypy or Ruff-clean, report the exact blocker
  rather than claiming full CI success.

## Risks

- Raising the baseline to Python 3.12 may affect users on older Python versions.
  This is intentional because the sibling repositories already use that
  baseline.
- Strict mypy/Ruff may expose pre-existing issues. The modernization should add
  the targets and fix narrow issues needed for the changed code, but not perform
  a broad type cleanup unless required.
- Dependency resolution may select newer FastMCP behavior. Runtime endpoint
  behavior should be guarded by the existing route tests.
