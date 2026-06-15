# Changelog

All notable changes to gnomad-link are documented here.

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
