# Stack And Agent Modernization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align `gnomad-link` with the modern Python, `uv`, and multi-agent conventions used by `pubtator-link` and `genereviews-link`.

**Architecture:** Runtime server boundaries remain unchanged. Tooling and documentation become `uv`-first, with `pyproject.toml`, `Makefile`, `AGENTS.md`, `CLAUDE.md`, and line-budget tooling serving as the agent-maintained development contract.

**Tech Stack:** Python 3.12+, FastAPI, FastMCP, Pydantic v2, gql/aiohttp, httpx, uv, hatchling, Ruff, mypy, pytest.

---

### Task 1: Capture Agent And Design Documentation

**Files:**
- Create: `docs/superpowers/specs/2026-05-25-stack-agent-modernization-design.md`
- Create: `docs/superpowers/plans/2026-05-25-stack-agent-modernization.md`
- Create: `AGENTS.md`
- Create: `CLAUDE.md`

- [x] **Step 1: Write the design spec**

Create the spec documenting the modernization scope, retained runtime
architecture, required checks, and risks.

- [x] **Step 2: Write this implementation plan**

Create the implementation checklist with exact files and verification commands.

- [x] **Step 3: Add shared agent guidance**

Create `AGENTS.md` with the project summary, source-of-truth rules, command
list, coding standards, gnomAD-specific constraints, MCP guidance, file-size
discipline, and testing notes.

- [x] **Step 4: Add minimal Claude Code entrypoint**

Create `CLAUDE.md` containing `@AGENTS.md` and only short Claude-specific
guidance.

### Task 2: Modernize Packaging And Commands

**Files:**
- Modify: `pyproject.toml`
- Modify: `Makefile`
- Create: `.pre-commit-config.yaml`
- Create: `.loc-allowlist`
- Create: `scripts/check_file_size.py`
- Modify: `README.md`

- [x] **Step 1: Update packaging metadata**

Switch to `hatchling`, Python `>=3.12`, modern bounded dependencies, dependency
groups, project scripts, package build metadata, Ruff settings, mypy settings,
pytest settings, and coverage settings.

- [x] **Step 2: Update Makefile**

Replace direct `pip`, Black, isort, and flake8 commands with `uv`-first
targets: `install`, `lock`, `sync`, `format`, `format-check`, `lint`,
`lint-ci`, `lint-fix`, `lint-loc`, `typecheck`, `typecheck-fast`,
`typecheck-stop`, `typecheck-fresh`, `test`, `test-fast`, `test-unit`,
`test-cov`, `check`, `ci-local`, `precommit`, `clean`, `dev`, `mcp-serve`, and
`mcp-serve-http`.

- [x] **Step 3: Add line-budget and pre-commit tooling**

Adapt the sibling `scripts/check_file_size.py` script for `gnomad_link`, add an
empty `.loc-allowlist`, and add pre-commit hooks for Ruff, mypy, and the
line-budget check.

- [x] **Step 4: Refresh README commands**

Update installation and development snippets to use `uv sync --group dev`,
`uv run`, and the new Makefile targets.

### Task 3: Remove The Undeclared CLI Health Dependency

**Files:**
- Modify: `gnomad_link/cli.py`
- Create: `tests/test_cli.py`

- [x] **Step 1: Write the failing regression test**

Add tests that patch `gnomad_link.cli.httpx.get` and verify successful and
failed health command behavior.

- [x] **Step 2: Run the focused test and confirm failure**

Run `uv run pytest tests/test_cli.py -q`. Expected before implementation:
collection or patch failure because `gnomad_link.cli` has no module-level
`httpx` dependency yet.

- [x] **Step 3: Implement minimal CLI change**

Import `httpx` and update `handle_health_command` to catch
`httpx.HTTPError`.

- [x] **Step 4: Run focused test and confirm pass**

Run `uv run pytest tests/test_cli.py -q`.

### Task 4: Lock And Verify

**Files:**
- Create: `uv.lock`

- [x] **Step 1: Resolve dependencies**

Run `uv lock`.

- [x] **Step 2: Verify file-size budget**

Run `make lint-loc`.

- [x] **Step 3: Run tests**

Run `make test`.

- [x] **Step 4: Run local CI**

Run `make ci-local`. If this exposes pre-existing strict Ruff or mypy issues,
capture the exact output and leave the repo with the modern CI target in place.

### Task 5: Add Docker Deployment Surface

**Files:**
- Create: `.dockerignore`
- Create: `.env.docker.example`
- Create: `docker/Dockerfile`
- Create: `docker/docker-compose.yml`
- Create: `docker/docker-compose.dev.yml`
- Create: `docker/docker-compose.prod.yml`
- Create: `docker/docker-compose.npm.yml`
- Create: `docker/README.md`
- Modify: `Makefile`
- Modify: `README.md`
- Modify: `docs/development.md`
- Modify: `AGENTS.md`
- Modify: `.gitignore`
- Create: `tests/unit/docker/test_dockerfile.py`
- Create: `tests/unit/docker/test_docker_compose.py`

- [x] **Step 1: Add the Docker image**

Create a multi-stage `docker/Dockerfile` using `python:3.14-slim`, `uv sync
--frozen --no-dev --active --no-install-project`, a copied virtual environment,
non-root `app` user, runtime directories under `/tmp/gnomad-link` and
`/var/cache/gnomad-link`, and default command:

```bash
gnomad-link --transport unified --host 0.0.0.0 --port 8000
```

- [x] **Step 2: Add Compose overlays**

Create a base service for unified REST plus MCP HTTP, a bind-mounted development
overlay, a production hardening overlay with read-only filesystem and dropped
capabilities, and an NPM overlay that removes host port publishing and attaches
to `${NPM_NETWORK_NAME:-npm_network}`.

- [x] **Step 3: Add Docker command wrappers and docs**

Add `docker-build`, `docker-up`, `docker-down`, `docker-logs`,
`docker-prod-config`, and `docker-npm-config` Makefile targets. Document the
workflow in `docker/README.md`, `README.md`, `docs/development.md`, and
`AGENTS.md`.

- [x] **Step 4: Add deterministic Docker tests**

Add unit tests that inspect Dockerfile and Compose text for the expected Python
base image, `uv.lock` install path, non-root runtime, unified HTTP MCP command,
Compose health checks, production hardening, and NPM network configuration.

- [x] **Step 5: Version the minimal Claude entrypoint**

Remove the stale `.gitignore` rule that ignored `CLAUDE.md`, preserving the
minimal `@AGENTS.md` Claude Code entrypoint as a tracked file.
