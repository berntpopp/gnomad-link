# AGENTS.md

Shared repository instructions for agentic coding tools working in gnomAD Link.

## Project

gnomAD Link is an MCP server for gnomAD; FastAPI is a thin host providing
`/health` only. The MCP facade covers gnomAD GraphQL allele frequency, gene,
transcript, ClinVar, structural variant, mitochondrial variant, region, and
liftover data.

Primary areas:

- `gnomad_link/` - Python package, MCP facade, GraphQL client, services,
  models, transports, and server management
- `gnomad_link/mcp/` - hand-authored MCP facade (tools, resources, errors)
- `gnomad_link/graphql/queries/` - versioned and shared GraphQL query documents
- `tests/` - unit and route tests
- `docs/` - architecture, API usage, MCP connection, and gnomAD reference docs
- `docker/` - Dockerfile, Compose overlays, and Docker deployment docs
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
- MCP tool names, schemas, resources, and response modes are owned by
  `gnomad_link/mcp/`. REST is intentionally minimal (`/health` only).
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
- `make run-prod`
- `make docker-build`
- `make docker-up`
- `make docker-down`
- `make docker-prod-config`
- `make docker-npm-config`

## Coding Standards

- Use `uv` for dependency management; do not use direct `pip` installs.
- Use modern Python typing: `list[str]`, `dict[str, int]`, `str | None`.
- Format and lint Python with Ruff.
- Type check with mypy targeting Python 3.12.
- Keep MCP tool behavior covered by unit tests; keep service behavior covered
  by unit tests.
- Keep GraphQL query changes paired with tests for query loading or affected
  tool/client behavior.
- Preserve MCP tool names and response schemas unless the task explicitly calls
  for a breaking change.
- Keep Docker production hardening in Compose overlays and keep the default
  image command on the unified FastAPI host plus MCP HTTP.

## Fleet Deploy Contract

- `docker/docker-compose.npm.yml` is the file the GeneFoundry fleet controller
  (`strato_v6_docker_npm`, `scripts/utils/deployment_preflight.py`) renders and
  validates. Every service there declares `user: "<uid>:<gid>"` numerically —
  this image's own value from `docker/Dockerfile` (currently `10001:10001`),
  never copied from a sibling `-link` repo; uid/gid differ per image.
- `user` must NOT appear in the Compose files listed in `container-release.json`
  (`docker-compose.yml`, `docker-compose.prod.yml`); the shared release gate
  (`container_release.py validate-compose`, `ALLOWED_SERVICE_KEYS`) forbids it
  there.
- Guard tests: `tests/unit/docker/test_docker_compose.py` —
  `test_npm_overlay_declares_numeric_user_for_every_service` and
  `test_release_compose_files_never_declare_user`.
- `container-release.json` declares `deployed_compose_files` (the full
  base+prod+npm list, in overlay order) so the shared reusable workflow's
  `validate-deployed-overlay` gate (`container_release.py
  validate-deployed-overlay`) checks the file set the controller actually
  deploys, not the release-only `compose_files`. `container-release.yml` and
  `container-ci.yml` both pin their shared workflow at `genefoundry-router`
  `v0.8.5` (`31ea81cee5475fc3655c047c63a89739948f99a9`) -- both must move
  together, since both validate `container-release.json` against the same
  `ReleaseConfig` pydantic schema (`extra="forbid"`); bumping only one leaves
  the other rejecting `deployed_compose_files` as an unknown field.
- Release checklist this repo enforces: bump `pyproject.toml` `version` by one
  PATCH, `uv lock`, add a `CHANGELOG.md` heading `## [x.y.z] - YYYY-MM-DD`,
  update `CITATION.cff`'s `version:` field only — it is a GENERATED file
  (`make citation-write` in `genefoundry-router`); no test in this repo pins
  `date-released` to the CHANGELOG or a literal, so leave it untouched unless a
  future test asserts otherwise — then tag `vx.y.z` and approve the `release`
  GitHub Environment gate via
  `gh api repos/berntpopp/gnomad-link/actions/runs/<id>/pending_deployments`
  (it can gate twice; `status: waiting` is the gate, not a slow build).

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

Hard cap: **600 lines per Python module** in `gnomad_link/`. Enforced by
`make lint-loc` (wired into `ci-local` and pre-commit). Tests are exempt.

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
