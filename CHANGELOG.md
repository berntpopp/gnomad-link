# Changelog

All notable changes to gnomad-link are documented here.

## [Unreleased]

### Changed

- Re-vendored the behaviour conformance gate from genefoundry-router `56db958`
  (`docs/conformance/behaviour.py` blob `c69801687`) so live MCP contract checks
  treat not-found example probes as inconclusive and keep empty auxiliary objects from hiding counted rows.

## [9.0.0] - 2026-07-15

MCP contract hardening: honest error envelopes, honest pagination, and a tool
surface an agent can trust. Research use only; not for clinical decision support.

### Changed (BREAKING)

- **`error_code` is now a closed 6-value enum**: `invalid_input`, `not_found`,
  `ambiguous_query`, `upstream_unavailable`, `rate_limited`, `internal`. Prior
  codes are folded in: `validation_failed`, `build_mismatch`, and
  `response_limit_exceeded` → `invalid_input`; `internal_error` and
  `output_validation_failed` → `internal`. The specific classification (e.g.
  `build_mismatch`) is preserved in a new `error_subtype` field, so callers keep
  the detail without switching on an open-ended code set.
- **Single required identifier parameters.** `get_gene_details`,
  `get_gene_summary`, and `compute_gene_carrier_frequency` now take one required
  `gene` (a symbol OR an Ensembl id); `get_coverage` and
  `search_structural_variants` take one required `target`; and
  `compute_variant_liftover`'s `source_genome` is now required. This replaces the
  prior "provide exactly one of `gene_symbol` / `gene_id` / …" optional pairs.
- **`get_gene_variants` `consequence` and `search_structural_variants` `sv_type`
  are now declared enums.** An out-of-vocabulary value is rejected with
  `invalid_input` instead of silently returning zero rows.

### Added

- **`isError: true` is now set on every error envelope**, per the MCP contract,
  so hosts and the router can detect a failed call without parsing the payload.
- **Honest pagination.** `get_gene_variants`, `search_genes`, `resolve_variant_id`
  and `search_variants` expose `total_count` and `has_more` that are invariant
  under `limit`; `get_region` reports true headline totals with the cap made
  explicit and sets `has_more` / `truncated` when the response is capped.
- **The `populations` filter is validated against the closed gnomAD ancestry
  vocabulary** at a shared layer (`get_variant_frequencies`, `get_variant_details`,
  `compute_carrier_frequency`, `compare_variant_across_datasets`): an unrecognised
  code is rejected as `invalid_input` naming the parameter, never a silently-empty
  breakdown.
- **A coordinate-shaped but invalid `target`** (e.g. a mitochondrial `MT-1-200`
  region) on `get_coverage` / `search_structural_variants` is rejected as
  `invalid_input` rather than silently reinterpreted as a gene symbol.
- **`compute_gene_carrier_frequency` now flags reduced- and variable-penetrance
  contributing variants** and carries a permanent caveat that gene-level
  ClinVar-P/LP estimates overestimate carrier frequency for genes with common
  reduced-penetrance alleles (e.g. CFTR).
- **`get_clinvar_variant_details` gained a `response_mode` (`compact` / `full`)**
  to trim per-submission provenance; its token-cost hint is corrected.
- Vendored **Behaviour Conformance v1** gate
  (`tests/conformance/behaviour.py` + `test_behaviour_v1.py`) wired into the
  `mcp-conformance` CI workflow after the transport probe.

### Fixed

- **Tool surface reduced from ~20.3k to under 10k tokens**: `outputSchema` is
  suppressed on every tool (including `get_server_capabilities`) and
  `dereference_schemas=False`.
- `get_variant_details`'s description no longer promises ClinVar annotation; it
  points to `get_clinvar_variant_details` instead.
- `get_gene_summary`'s `next_commands` entry for `get_clinvar_variant_details`
  now carries a real `variant_id` (or is omitted) rather than a placeholder.
- **Reduced-penetrance flagging is derived from real ClinVar semantics**: only a
  Pathogenic/Likely-pathogenic call carrying a penetrance qualifier is flagged;
  Benign, Uncertain-significance and Conflicting classifications are no longer
  false-positives.
- **Recovery `next_commands` are callable under the collapsed identifiers**:
  emitters that pointed at `search_structural_variants(region=…)`,
  `get_gene_details(dataset=…)`, or `search_structural_variants({})` now use the
  required `target` / `gene` surface or a callable discovery fallback.
- **The output-schema-validation error envelope keeps its `structuredContent`**
  (it previously nulled it on the `isError` result).
- **`get_gene_summary` compact mode no longer drops `pext.regions` silently**: it
  emits a `truncated_pext` marker with a `response_mode='full'` restore hint, and
  the mode is documented.

## [8.0.5] - 2026-07-14

### Fixed

- **The NPM deployment would have lost its public hostname on the next deploy.**
  `docker-compose.prod.yml` sets `container_name: !reset null`, which is right for the
  standalone production stack it targets. But the deployed chain is
  `docker-compose.yml -f docker-compose.prod.yml -f docker-compose.npm.yml`, and Nginx
  Proxy Manager forwards to a **container name** on the shared network — the live proxy
  host emits `proxy_pass http://gnomad_link_server:8000;`. With the name reset and nothing
  restoring it, Compose would have named the container `gnomad-link-gnomad-link-1`, NPM
  could not have resolved it, and `gnomad-link.genefoundry.org` would have started
  returning 502 the moment the server pulled this compose. `docker-compose.npm.yml` now
  restores `container_name: gnomad_link_server`. `docker-compose.prod.yml` is untouched.

### Added

- `GNOMAD_LINK_IMAGE` in `.env.docker.example`. The prod overlay has always required it
  (it fails closed without it), but it was documented nowhere an operator would copy.

## [8.0.4] - 2026-07-13

### Fixed

- Re-pin the reusable container CI and container release workflows to the
  corrected GeneFoundry container release standard revision
  (`58d011d9c72efe90337244342fdec703f2b5b4b9`). The previously pinned revision
  carried latent release-pipeline defects that were fixed centrally, including
  GHCR authentication before the version alias push. Research use only; not for
  clinical decision support.

## [8.0.3] - 2026-07-13

### Build

- Adopt the GeneFoundry container-release standard: add SHA-pinned central
  container CI/release callers, typed `container-release.json`, digest-only
  production Compose, complete OCI image labels, and normalized Docker context
  exclusions. Research use only; not for clinical decision support.

## [8.0.2] - 2026-07-11

### Security (defense in depth)

- Guard the FastMCP-core not-found reflection surface. FastMCP core echoed the
  caller's own requested tool name / resource URI / prompt name (with any
  control/zero-width/bidi/NUL code points) back to the caller and to logs before
  backend middleware ran. A new `NotFoundGuard` middleware preflights the tool
  name (unknown -> fixed name-free `not_found` envelope) and fixes the
  `on_read_resource` boundary; a protocol-handler backstop replaces the
  unknown-tool return path and the unknown-prompt / malformed-resource dispatch
  errors with fixed input-free messages; and a validation-log scrub filter
  neutralizes the FastMCP/MCP-SDK records that reflected the raw name/URI. The
  requested name is never fed into the cross-session `get_diagnostics` error
  rings. Caller self-reflection surface (low-medium); no success or error
  envelope schema changed. Research use only.

## [8.0.1] - 2026-07-11

### Security (defense in depth)

- Caller-visible error messages are sanitized of control/zero-width/bidi/NUL
  code points; the upstream gnomAD GraphQL error text (including
  transport-exception bodies) is no longer echoed into MCP messages; the gql
  transport DEBUG body-logging is pinned off. Research use only.

## [8.0.0] - 2026-07-11

### Changed (BREAKING)

- **ClinVar submitter/condition prose is now fenced as a Response-Envelope
  Standard v1.1 `untrusted_text` typed object.** `get_clinvar_variant_details`
  surfaces two ClinVar submitter-authored free-text fields verbatim through
  gnomAD's `clinvar_variant` GraphQL passthrough:
  `submissions[*].conditions[*].name` and `submissions[*].submitter_name`.
  Both fields changed from a bare JSON string to
  `{kind: "untrusted_text", text, provenance: {source, record_id,
  retrieved_at}, raw_sha256}` -- defense in depth so the router and any host
  treat retrieved ClinVar prose as data, never instructions. This is a
  breaking reshape (not an additive dual-field); callers reading either field
  as a plain string must update to read `.text`. Frequency/constraint output
  elsewhere in this server is numeric and unaffected. The v1.1 object/byte
  ceilings are enforced over the EMITTED (post-`submissions_limit`) submissions
  only, so a large upstream ClinVar record never trips the limit when the
  capped response it returns is small.

### Added

- New error envelope `error_code: "response_limit_exceeded"`
  (`recovery_action: "reformulate_input"`, non-retryable) returned when a
  fenced response would exceed a Response-Envelope v1.1 object-count/byte
  ceiling. Distinct from `validation_failed` (caller input) and
  `internal_error`; recover by requesting fewer records.

## [7.0.0] - 2026-07-10

### Security

- Replace the disabled FastMCP Host/Origin protection with strict validation on
  the outer ASGI application and the native MCP transport. Untrusted Host values
  are rejected on health and MCP routes; browser Origin values must be
  same-origin or explicitly approved.
- Reject wildcard Host patterns and declare the production proxy hostname and
  loopback health-check Host explicitly in the supplied Compose profiles.

### Changed (BREAKING)

- Custom reverse-proxy deployments must add their exact public hostname to
  `MCP_ALLOWED_HOSTS`. JSON lists are accepted; the safe default permits only
  localhost and loopback addresses.

## [6.0.4] - 2026-07-10

### Fixed

- Preserve sanitized `validation_failed` MCP envelopes with FastMCP 3.4.4 by unwrapping only
  framework validation errors caused by pre-body Pydantic argument validation. Framework errors
  without that cause continue to propagate and are not mislabeled as caller input failures.

### Build

- Upgrade FastAPI to 0.139.0, Uvicorn to 0.51.0, FastMCP to 3.4.4, Ruff to 0.15.21,
  mypy to 2.2.0, mkdocstrings to 1.0.5, and `astral-sh/setup-uv` to the immutable v8.3.2
  commit. Dependency PR #32 supersedes the automatically closed #29.

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
