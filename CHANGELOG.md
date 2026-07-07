# Changelog

All notable changes to gnomad-link are documented here.

## [6.0.3] - 2026-07-07

Security remediation (fleet audit 2026-07-06).

- **No PII in the caller-facing diagnostics rings (finding M4).** `get_diagnostics`
  returns two process-global rings to any caller, so one caller's variant
  coordinates / rejected input could leak cross-session. The error and
  schema-drift recorders no longer retain raw exception text (`message` /
  `raw_message`) or raw upstream drift text; each record reduces to non-PII
  fields only (`tool_name` + `error_code` + `exc_type`; `tool_name` +
  `error_field`). A regression test asserts a sentinel never survives into the
  diagnostics output.
- **Loopback-bind the base compose host port.** The base
  `docker/docker-compose.yml` now publishes on `127.0.0.1` so copying it to a
  server never exposes the unauthenticated backend on the public IP (Docker
  otherwise binds `0.0.0.0` and bypasses the host firewall). Production still
  fronts the container via the reverse-proxy overlays (`ports: !reset []`). A
  guard test enforces the loopback bind.

## [6.0.2] - 2026-07-03

Advertise the gnomAD Link **package version** in the MCP `initialize`
handshake, and standardize version single-sourcing. The `FastMCP(...)`
constructor was built without a `version=` argument, so `serverInfo.version`
reported the FastMCP framework version (e.g. `3.4.2`) instead of the real
package version. The facade now passes `version=__version__`, so
`serverInfo.version` matches `/health` and the installed distribution metadata.

The version is now single-sourced from `pyproject.toml` (`[project].version`):
`gnomad_link.__version__` is derived from the installed distribution metadata
via `importlib.metadata.version("gnomad-link")` (previously a hardcoded literal
in `gnomad_link/__init__.py` with hatch reading it back as a dynamic version).
Future bumps only edit `pyproject.toml`. A regression test locks the contract
(pyproject -> metadata -> `__version__` -> `serverInfo.version`).

## [6.0.1] - 2026-06-29

Adopt the **GeneFoundry Container & Deployment Hardening Standard v1** (closes #19):
pin the base image by digest (`python:3.14-slim@sha256:b877e50…`) and never send
CORS credentials with a wildcard origin.

## [6.0.0] - 2026-06-16

Adopt the **GeneFoundry Logging & CLI Standard v1**: a `typer` CLI, `structlog`
structured logging, and Streamable-HTTP-only transport.

### Changed (BREAKING)

- **CLI is now a `typer` app** (`gnomad_link.cli:app`). Server start is always
  `gnomad-link serve …` — the previous bare `gnomad-link --transport …`
  invocation is gone. Commands: `serve` (`--transport {unified,http}` default
  `unified`, `--host`, `--port`, `--mcp-path`, `--log-level`, `--disable-docs`,
  `--dev`), `config [--validate]`, `health [--url]`, `cache stats|clear`,
  `version`.
- **Single console script** `gnomad-link = "gnomad_link.cli:app"`. The
  `gnomad-link-mcp` script and the root `server.py` / `mcp_server.py` entry
  points are deleted.
- **stdio transport removed.** The fleet is Streamable-HTTP-only: `stdio` is
  dropped from `ServerConfig.transport` / `Settings.MCP_TRANSPORT`, the
  `start_stdio_server` path and stdio logging branch are deleted, and the dead
  `gnomad_link/transports/` package is removed.
- **Logging migrated from stdlib to `structlog`** (`gnomad_link/logging_config.py`):
  canonical processor chain (`merge_contextvars → add_log_level →
  TimeStamper(iso) → StackInfoRenderer → format_exc_info → static fields`),
  JSON in production and `ConsoleRenderer` in development (selected by
  `LOG_FORMAT`, default `json`), with `asgi-correlation-id` bound into every
  event. The `TransportAwareFormatter` and `get_*_logger` helpers are removed;
  call sites use `structlog.get_logger(__name__)`. `STDIO_LOG_LEVEL` /
  `MCP_LOG_LEVEL` settings are replaced by `LOG_FORMAT`.

### Added

- CLI tests via `typer.testing.CliRunner` and `tests/unit/test_logging_config.py`
  asserting the canonical JSON event shape and bound `correlation_id`.

## [5.0.0] - 2026-06-15

Adopt the **GeneFoundry Tool-Naming Standard v1** so the server composes cleanly
behind `genefoundry-router` (tools surface as `gnomad_<tool>` at the gateway).

### Changed (BREAKING)

- Renamed the discovery tool `get_gnomad_diagnostics` → **`get_diagnostics`**. The
  embedded `gnomad` source token was redundant under the gateway's `gnomad_`
  namespace prefix (it produced `gnomad_get_gnomad_diagnostics`). The
  gateway-qualified name is now `gnomad_get_diagnostics`. The payload, behaviour,
  and the underlying service method are unchanged; update any direct callers of
  the tool name.
- Renamed the liftover tool `liftover_variant` → **`compute_variant_liftover`**.
  `liftover` is not in the Standard v1 canonical verb set
  (`get|search|list|resolve|find|compare|compute`); the operation is a coordinate
  computation, so it now uses the canonical `compute` verb. The payload and
  behaviour are unchanged.
- Dropped the deprecated `reference_genome` alias on the liftover tool. Use the
  canonical **`source_genome`** parameter instead (the only accepted way to
  declare the build of `source_variant_id`). No deprecation shim is retained.

### Added

- Tool-name compliance test (`tests/unit/test_tool_names.py`): every registered
  tool must match `^[a-z0-9_]{1,50}$`, start with a canonical verb
  (`get|search|list|resolve|find|compare|compute`), and not self-prefix the
  `gnomad` namespace token.
- README documents the canonical gateway **namespace token** `gnomad`.

### Fixed

- Reconciled the package version (`pyproject.toml` was `2.0.0`, `__init__.py` was
  `4.0.0`) to a single `5.0.0`.

## [2.0.0]

Prior release. Unified server providing REST API and MCP interfaces for gnomAD
allele-frequency data (variant/gene/region/coverage/structural/mitochondrial
queries, carrier-frequency computation, ClinVar enrichment, and cross-dataset
comparison).
