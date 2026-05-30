# MCP Reliability Hardening — Execution Plan

Date: 2026-05-30
Spec: `docs/superpowers/specs/2026-05-30-mcp-reliability-hardening-design.md`

Order: P0 (correctness/availability) → P1 (guidance/output correctness) →
P2 (token efficiency) → findings outside the research punch-list (M-4, L-1) →
verification. TDD per task; atomic commit per task; `make ci-local` at the end.

## P0

- [x] **H-1** unwrap `get_variant_details` + not_found guard + regression test. (351b918)
- [ ] **M-3a** `base_client`: persistent reconnecting session, lazy double-checked
  lock bootstrap, `asyncio.Semaphore(GNOMAD_MAX_CONCURRENCY)`, `backoff` retry with
  full jitter on retryable transport codes; idempotent `close()` closing the session.
  Add `GNOMAD_MAX_CONCURRENCY` to settings. Update `test_base_client.py` to the new
  seam; add concurrency + retry tests (fake session). 
- [ ] **M-3b** `server_manager` FastAPI lifespan teardown closes the service.
- [ ] **M-2a** `base_client`: `UpstreamInputError` + `RateLimitedError`; classify
  GraphQL-validation phrasing → `UpstreamInputError`, 429 → `RateLimitedError`; keep
  `not found` → `DataNotFoundError`; everything else → `GnomadApiError`. Tests per phrase.

## P1

- [ ] **M-2b** `errors.py`: add `invalid_input` (non-retryable) + `rate_limited`
  (retryable) codes, isinstance-checked before `GnomadApiError`; context-aware
  `fallback_tool`/`fallback_args` from `McpErrorContext`. Tests (envelope passthrough).
- [ ] **M-1a** `schema_relax`: nullable-ize bare scalar types (skip enum/const,
  skip containers). Unit tests: null-bearing BND schema accepts; enum still rejects.
- [ ] **M-1b** `structural_variant_models`: make `end`/`af`/`pos`/`ac`/`an`/`chrom`
  Optional where genuinely nullable. Tests.

## P2

- [ ] **M-1c / L-3** `sv_shaping`: `shape_structural_variant` trims heavy
  distributions + drops duplicated top-level `genes`; wire into `get_structural_variant`
  with `response_mode` (compact default). Fix token hint. Tests per SV class.
- [ ] **L-4** `gene_summary` section/`include_*` projection (decouple full-ClinVar);
  document token deltas. Tests (clinvar-excluded, expression-only).
- [ ] **Token hints** convert drift-prone kB hints to parameter-anchored ranges;
  optional measured `token_estimate` in `_meta`.

## Findings outside the research punch-list

- [ ] **M-4** `get_transcript_details`: unwrap; best-effort GTEx via gene path +
  compact top-tissues summary; correct description. Tests.
- [ ] **L-1** `liftover_variant`: `build_note` when results empty. Test.

## Verification

- [ ] Update `resources.py` token hints; capabilities parity (`test_mcp_facade_surface`).
- [ ] `make ci-local` green (format, lint, lint-loc, typecheck, tests).
- [ ] Rebuild Docker MCP; live-smoke every fixed tool (variant details, each SV
  class incl. CPX/BND, BRCA2→invalid_input, transcript GTEx, liftover note,
  heteroplasmy trim).
- [ ] Present finishing-a-development-branch options (no merge/push without go-ahead).
