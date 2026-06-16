# CI/CD, Sibling-Aligned Release/Versioning, and v2/v3 Test Coverage — Design

Status: draft
Date: 2026-06-16
Owner: gnomAD Link

## Motivation

A triage of the seven open GitHub issues (filed Jul 2025, before the repo's
pivot to an MCP-first architecture) against the current `main` (HEAD `7ef9627`)
and against the sibling `*-link` repos found that the architecture issues are
already solved and the remaining value is in tooling and test breadth:

| # | Issue | Verdict | Disposition |
|---|-------|---------|-------------|
| #1 | unify FastAPI + FastMCP | Done/superseded — single `server_manager.py` mounts MCP on FastAPI via `app.mount()` (`server_manager.py:133-135`), shared `app.state.frequency_service` | **Closed with evidence** |
| #6 | onion architecture | Done/superseded — `api/` -> `services/` -> `models/` -> `mcp/` layering realized; rich-REST layer intentionally dropped | **Closed with evidence** |
| #7 | error handling | Largely done — deterministic MCP error envelopes (`mcp/errors.py`) + taxonomy tests; REST is `/health`-only | **Closed with evidence** |
| #4 | CI/CD GitHub Actions | **Not started — no `.github/` at all** | **This spec** |
| #2 | semantic versioning | Not started; no sibling uses python-semantic-release | **This spec (sibling-aligned)** |
| #3 | docs site / Pages | Not started; no sibling ships a docs site | **Deferred** (note on issue) |
| #5 | v2/v3 test coverage | Partial — r2_1/r3/r4 supported in code; no systematic cross-version tests | **This spec (focused top-up)** |

`make ci-local` already exists and is the project's canonical gate
(`format-check lint-ci lint-loc typecheck-fast test-fast eval-ci`). The single
biggest gap is that **nothing runs it on GitHub**. The sibling repos
(`gtex-link`, `pubtator-link`, `genereviews-link`, `litvar-link`,
`autopvs1-link`) all share an identical, proven `.github/` layout. This spec
ports that layout, adds a sibling-aligned tag-triggered release, single-sources
the version, and adds focused deterministic v2/v3/v4 tests.

## Scope

In scope (three independent workstreams, parallelizable — disjoint paths):

- **A — CI/CD bundle (#4):** `.github/workflows/{ci,security,docker,container-security}.yml`, `.github/dependabot.yml`, `.github/pull_request_template.md`.
- **B — Release + versioning (#2):** `.github/workflows/release.yml`, conventional-commit + release docs, version single-sourced to `gnomad_link/__init__.py`.
- **C — v2/v3/v4 tests (#5):** parametrized deterministic unit tests under `tests/unit/`.

Out of scope (explicit):

- Rich REST API / Layer-3 endpoints (project is MCP-first; REST = `/health`).
- python-semantic-release auto-bump on push to `main` (issue #2's literal spec; rejected as non-sibling-aligned — releases stay tag-driven and intentional).
- MkDocs / GitHub Pages docs site (#3, deferred — siblings keep curated in-repo `docs/`).
- PyPI publishing in CD. Siblings do not auto-publish; release validates + builds the Docker image. (Can be added later behind a trusted-publisher flow.)
- Multi-Python test matrix. `requires-python >=3.12` and `make ci-local` is single-version; siblings test 3.12 only. No 3.9-3.11 matrix (issue #4's example is stale — the project dropped <3.12).
- Live gnomAD calls in default CI (integration tests stay `integration`-marked and out of `ci.yml`).

## Workstream A — CI/CD bundle (#4)

Port the sibling template verbatim in structure, adapted to gnomAD Link's Make
targets and Docker layout. All third-party actions **SHA-pinned** with a version
comment (matches siblings; satisfies the supply-chain posture). Every workflow:
`concurrency` group with `cancel-in-progress`, `permissions: contents: read` by
default, `uv` with cache, `uv sync --group dev --frozen`.

### `ci.yml`
- Triggers: `pull_request`, `push` to `main`.
- One `quality` job (ubuntu-latest, Python 3.12): checkout -> setup-python -> setup-uv -> `uv sync --group dev --frozen` -> `make ci-local` -> `make test-cov`.
- Mirror of `gtex-link/.github/workflows/ci.yml`. `make ci-local` already includes format-check, lint, lint-loc, typecheck, test-fast, and the deterministic eval harness, so CI == local gate.

### `security.yml`
- Triggers: `pull_request`, `push` to `main`, weekly cron.
- `codeql` job (Python, `build-mode: none`, gated `if: !github.event.repository.private`, `security-events: write`).
- `dependency-review` job (PR-only, `continue-on-error: true`).
- Mirror of `gtex-link/.github/workflows/security.yml`.

### `docker.yml`
- Triggers: PR + push to `main`, path-filtered (`docker/**`, `pyproject.toml`, `uv.lock`, the workflow itself).
- `validate-compose` job: render compose via the repo's own Make targets — `make docker-prod-config` and `make docker-npm-config` (these wrap `docker compose ... config`, keeping CI and local identical).
- `build-image` job: `docker build -f docker/Dockerfile -t gnomad-link:ci .`.

### `container-security.yml`
- Triggers: PR + push to `main`, weekly cron.
- Build `gnomad-link:scan`, Trivy vulnerability scan (table, `exit-code: 0` — report-only), Trivy SBOM (CycloneDX), upload artifacts.
- Mirror of `pubtator-link/.github/workflows/container-security.yml`.

### `dependabot.yml`
- Ecosystems: `uv` (`/`, grouped weekly), `github-actions` (`/`, weekly), `docker` (`/docker`, weekly).
- Mirror of `gtex-link/.github/dependabot.yml`.

### `pull_request_template.md`
- Summary / Type (conventional-commit categories) / Verification (`make ci-local` passes, tests added, CHANGELOG updated) / Breaking changes. Mirror of `gtex-link` template.

## Workstream B — Release + versioning (#2, sibling-aligned)

The repo already uses Conventional Commits (`feat!:`, `fix(mcp):`, `docs(...)`,
`build(...)` throughout `git log`) and keeps a hand-maintained `CHANGELOG.md`.
Sibling practice is **manual, intentional version bumps + a tag-triggered
release-validation workflow** — not auto-bump. We match that and add one guard
the siblings lack: the release asserts the git tag matches the package version.

### `release.yml`
- Trigger: `push` tags `v*`.
- `release-validation` job: checkout -> setup-python/uv -> `uv sync --group dev --frozen` -> `make ci-local` -> `make docker-prod-config` -> `make docker-npm-config` -> `docker build -f docker/Dockerfile -t gnomad-link:release .`.
- **Tag/version guard:** a step asserts the tag (`${GITHUB_REF_NAME#v}`) equals `gnomad_link.__version__`, failing the release on drift. Mirror of `gtex-link/release.yml` + the guard.

### Version single-sourcing
Today the version string is duplicated in three places: `pyproject.toml:7`,
`gnomad_link/__init__.py:3`, `server_manager.py:64`. Collapse to one source:

- `pyproject.toml`: `[project]` gains `dynamic = ["version"]` (drop the static `version = "5.0.0"`); add `[tool.hatch.version] path = "gnomad_link/__init__.py"`.
- `gnomad_link/__init__.py`: `__version__ = "5.0.0"` becomes the single source of truth (hatchling reads it at build time).
- `server_manager.py:64`: replace the hardcoded `version="5.0.0"` with `from gnomad_link import __version__`.

This is backward-compatible (wheel still gets a concrete version) and makes the
release tag/version guard meaningful.

### Docs
- `CONTRIBUTING.md` (new) or a `docs/development.md` section: Conventional Commits convention + the "bump `__version__`, update CHANGELOG, tag `vX.Y.Z`, push tag" release recipe. `commit-msg` validation via pre-commit is **optional/deferred** (no sibling enforces it in-repo; the PR template's Type checklist covers it).

## Workstream C — v2/v3/v4 test coverage (#5, focused)

The premise of issue #5 ("v4 only") is already false: `models/enums.py:9-11`
defines `GNOMAD_R2_1`/`GNOMAD_R3`/`GNOMAD_R4`, `graphql/queries/v2|v3` exist, and
there is a live r2_1 regression. The real gap is **systematic, deterministic
cross-version unit coverage**. Add a small parametrized layer (no network; use
the existing `respx` dev dep and the query loader/builder which are pure):

- **C1 — query selection per dataset (pure, highest value):** parametrize over `(gnomad_r2_1 -> v2, gnomad_r3 -> v3, gnomad_r4 -> v4/shared)` and assert the loader/builder selects the correct versioned GraphQL document and includes/excludes version-specific fields. Grounded in `graphql/query_builder.py` + `query_loader.py` (exact assertions finalized against source during planning).
- **C2 — frequency shaping per version (respx-mocked):** minimal per-version upstream response fixtures exercising one version-divergent field (e.g. v2 `popmax` vs v4 `grpmax`/joint) through the frequency service/shaping; assert no cross-version regression. Fixtures kept minimal (not the full `tests/test_data/{v2,v3,v4}` reorg from #5's maximal spec).
- **C3 — version-aware error path:** assert build/dataset-mismatch handling (`mcp/build_check.py`, `BuildMismatchError`) behaves per version.

Coverage target: keep `make test-cov` above its configured floor; new tests run
inside the new `ci.yml`. Tests live under `tests/unit/` (no alternate root, per
AGENTS.md). All deterministic — zero live gnomAD calls.

## Invariants

- Additive and non-breaking: no MCP tool-name/schema changes, no REST changes.
- <=600 LOC/module (`mcp/errors.py`, `mcp/shaping.py` near cap — no growth).
- No new runtime dependencies. Workstream C uses existing `respx`/`pytest`.
- Default CI never hits the live gnomAD API; integration tests stay `integration`-marked and excluded from `ci.yml`.
- Actions SHA-pinned with version comments.
- Research-use scope only; no clinical-decision-support implications.

## Definition of Done

- [ ] `.github/` contains `ci.yml`, `security.yml`, `docker.yml`, `container-security.yml`, `release.yml`, `dependabot.yml`, `pull_request_template.md`; all actions SHA-pinned.
- [ ] `ci.yml` runs `make ci-local` + `make test-cov` and is green on a PR.
- [ ] Version is single-sourced to `gnomad_link/__init__.py`; `pyproject.toml` is dynamic; `server_manager.py` imports it; `release.yml` guards tag==version.
- [ ] Conventional-commit + release recipe documented.
- [ ] Parametrized v2/v3/v4 unit tests added and green under `make test-fast`; `make test-cov` stays above floor.
- [ ] `make ci-local` green locally before handoff.
- [ ] #3 annotated as deferred (sibling-aligned) on the issue; #4/#2/#5 referenced from their PR(s).

## Execution / parallelism

Workstreams A, B, C touch disjoint paths (`.github/` vs `pyproject.toml`+2 src
lines vs `tests/`), so they can be implemented and committed in parallel and
land as one PR (or three focused commits). A is the highest-value, lowest-risk
piece and should land first so B/C are validated by the new CI.
