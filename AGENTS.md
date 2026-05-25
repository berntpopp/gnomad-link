# AGENTS.md

Shared repository instructions for agentic coding tools working in gnomAD Link.

## Project

gnomAD Link is a Python FastAPI and MCP server for gnomAD GraphQL allele
frequency, gene, transcript, ClinVar, structural variant, mitochondrial variant,
region, and liftover data.

Primary areas:

- `gnomad_link/` - Python package, FastAPI routes, GraphQL client, services,
  models, transports, and server management
- `gnomad_link/graphql/queries/` - versioned and shared GraphQL query documents
- `tests/` - unit and route tests
- `docs/` - architecture, API usage, MCP connection, and gnomAD reference docs
- `docs/superpowers/specs/` - design specs for agentic workers
- `docs/superpowers/plans/` - implementation plans for agentic workers

## Source Of Truth

- Use this file for shared repo-wide agent guidance.
- Keep `CLAUDE.md` lean and Claude-specific; it should reference this file and
  not duplicate shared policy.
- Prefer `Makefile` targets over ad hoc commands.
- Use `uv.lock` as the dependency lock source of truth.
- Keep generated GraphQL reference docs under `docs/gnomad_graphql/`.
- For multi-step work, write or update the spec in `docs/superpowers/specs/`
  and the execution plan in `docs/superpowers/plans/` before broad edits.
- Claude Code, Codex, and other coding agents should all follow this file first,
  then their tool-specific entrypoint files.

## Working Rules

- Do not revert or overwrite changes you did not make unless explicitly asked.
- Keep edits scoped to the task and avoid unrelated refactors.
- Prefer existing code patterns over new abstractions.
- Put tests under `tests/`; do not create alternate test roots.
- Use ASCII unless a file already requires non-ASCII content.
- Treat gnomAD as an external research data service. Do not add destructive
  public MCP tools such as cache clearing unless they remain excluded from MCP.
- Keep MCP tools research-use scoped and avoid implying clinical decision
  support.
- Keep live upstream calls out of the default local CI path. Tests that require
  gnomAD API availability or quota must be marked `integration`.
- Keep agent-visible docs concise and operational. Prefer commands, boundaries,
  and invariants over prose that will drift.

## Commands

Required checks before claiming completion:

- `make ci-local`

Useful focused commands:

- `make install`
- `make lock`
- `make sync`
- `make format`
- `make format-check`
- `make lint`
- `make lint-fix`
- `make lint-loc`
- `make typecheck`
- `make typecheck-fast`
- `make test`
- `make test-fast`
- `make test-unit`
- `make test-integration`
- `make test-cov`
- `make precommit`
- `make dev`
- `make mcp-serve`
- `make mcp-serve-http`

## Coding Standards

- Use `uv` for dependency management; do not use direct `pip` installs.
- Use modern Python typing: `list[str]`, `dict[str, int]`, `str | None`.
- Format and lint Python with Ruff.
- Type check with mypy targeting Python 3.12.
- Keep FastAPI route behavior covered by route tests and service behavior
  covered by unit tests.
- Keep GraphQL query changes paired with tests for query loading or affected
  route/client behavior.
- Preserve public REST paths, MCP tool names, and response schemas unless the
  task explicitly calls for a breaking change.

## Agentic Development

- Start by reading the relevant route, service, model, GraphQL query, and test
  files before editing.
- Keep implementation plans bite-sized and check off steps as they are
  completed.
- Prefer focused commits that match the plan task boundaries.
- When tests fail, identify whether the failure is deterministic local behavior
  or live upstream state before changing production code.
- Use `make test-integration` only when the task intentionally touches live
  gnomAD behavior or when validating a release candidate.
- Do not broaden Ruff or mypy ignores to hide new issues. Existing relaxations
  in `pyproject.toml` are transitional compatibility settings; tighten them when
  touching the relevant files.

## File Size Discipline

Hard cap: **600 lines per Python module** in `gnomad_link/`, `server.py`, and
`mcp_server.py`. Enforced by `make lint-loc` (wired into `ci-local` and
pre-commit). Tests are exempt.

Why: large modules concentrate complexity, slow mypy and import cost, and
degrade LLM-assisted refactors. When a file approaches 500 lines, plan its
split.

How:

- New files MUST stay under 600 lines.
- Existing oversized files are grandfathered in `.loc-allowlist` with their
  current line count as the ceiling. They may shrink but not grow.
- Prefer cohesive splits: one module per responsibility, not random partitioning
  to fit under the cap.
- Keep public protocols, facades, route behavior, and MCP tool names stable
  across splits so call sites do not churn.
- If you must add to an allowlisted file as part of an unrelated fix, raise the
  ceiling explicitly in `.loc-allowlist` in the same commit and link the
  decomposition plan in the message.

## Testing Notes

- `make test` is the fast default and runs deterministic tests from
  `tests/unit/`.
- `make test-integration` runs live gnomAD API tests and may fail when the
  upstream API rate-limits requests.
- `make test-cov` runs coverage with the configured floor.
- `make ci-local` runs formatting, linting, line-budget checks, type checking,
  and tests.
- Treat failing checks as real issues unless you have clear evidence otherwise.
