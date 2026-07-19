# MCP Reliability Hardening — Design Spec

> Historical record

Date: 2026-05-30
Branch: `feat/mcp-reliability-hardening`
Status: in progress

## Motivation

A full-tool live review of the gnomAD Link MCP (21 tools, server v2.0.0, gnomAD
4.1.0) scored the architecture 9-10 but reliability 7.5/10. This spec captures
the fixes that take reliability past 9.5 without touching the strong scaffolding
(error envelopes, `truncated`/`to_restore` hints, `next_commands`, token hints,
capabilities surface). Findings were reproduced against the live server and
root-caused in current-`main` source; best practices were researched against gql
3.5.3 source, the MCP spec, JSON Schema 2020-12, and Anthropic tool-design docs.

## Findings → root cause → fix

### H-1 (HIGH) `get_variant_details` silent-empty payload
- Root cause: `service.get_variant` returns the GraphQL wrapper `{"variant": {...}}`;
  the tool fed that straight into `shape_variant_details_compact`, whose keep-set
  keys live one level deeper, so the projection matched nothing → bare `{_meta}`.
  Unlike the SV/mito/region tools, it never unwrapped.
- Fix: unwrap `raw.get("variant", raw)` before shaping; return the unwrapped block
  in full mode; raise `VariantNotFoundError` on an absent variant (never silently
  empty). **DONE** (commit 351b918).

### M-3 (MEDIUM) No concurrency safety / 429 smoothing
- Root cause (verified in gql 3.5.3 source): one shared `AIOHTTPTransport` + the
  one-shot `Client.execute_async` (which connects AND closes the transport every
  call). Two concurrent calls race → `TransportAlreadyConnected`; unbounded fan-out
  trips gnomAD's rate limiter (429 storm).
- Fix: ONE persistent reconnecting session per client (`connect_async(reconnecting=True)`),
  opened lazily under a double-checked `asyncio.Lock`, reused across concurrent
  tasks via `session.execute(...)`; bound by an `asyncio.Semaphore`
  (`GNOMAD_MAX_CONCURRENCY`, default 5); a `backoff` retry layer with full jitter on
  `TransportServerError.code in {429,500,502,503,504}` + `TransportClosed`/`TimeoutError`.
  `close()` becomes idempotent and closes the session; FastAPI lifespan teardown
  closes the service. Do NOT retry `TransportQueryError` (business errors).

### M-2 / L-5 (MEDIUM/LOW) Error taxonomy + fallback
- Root cause: base_client collapses every non-"not found" `TransportQueryError`
  into `GnomadApiError` → errors.py maps to `upstream_unavailable`/`retryable=true`,
  so a deterministic input error ("Unrecognized query.") tells the LLM to retry
  forever. `not_found` fallback is hard-coded to `search_genes` for every tool.
- Fix: classify at the base_client boundary into a new `UpstreamInputError`
  (GraphQL-validation phrasing) and `RateLimitedError` (429); errors.py adds
  non-retryable `invalid_input` and retryable `rate_limited`, isinstance-checked
  BEFORE `GnomadApiError`. Make `fallback_tool`/`fallback_args` context-aware from
  `McpErrorContext`: variant tools → `resolve_variant_id`, gene/transcript tools →
  `search_genes`, else `get_server_capabilities`. Invariant: `retryable=true` ⇒
  identical call may later succeed; `false` ⇒ never.

### M-1 / L-3 (MEDIUM/LOW) SV output null-safety + duplication
- Root cause: `StructuralVariant` types `end`/`af`/`pos`/`ac`/`an` as non-nullable,
  but BND/CTX/CPX classes return null → MCP output-schema validation rejects with
  "Output validation error". `relax_output_schema` strips `required` but leaves
  scalar `type` intact, so it does not help. Also `genes` is duplicated (top-level
  + `consequences[].genes`); token hint understated (~1-3kB vs ~15kB).
- Fix: extend `relax_output_schema` to nullable-ize BARE scalar types via the
  `["integer","null"]` idiom (skip any node with `enum`/`const`; skip object/array
  containers). Make genuinely-nullable SV model fields `Optional`. Add
  `shape_structural_variant` to trim heavy histograms and drop the duplicated
  top-level `genes`. Correct the token hint.

### M-4 (MEDIUM) `get_transcript_details` GTEx absent
- Root cause: the v4 transcript query never requests `gtex_tissue_expression` (the
  standalone `transcript()` GTEx field is unavailable on GRCh38 / errors on GRCh37);
  payload is also wrapped under `transcript`.
- Fix: unwrap; best-effort enrich GTEx via the working gene path
  (`gene.transcripts[].gtex_tissue_expression`, already used by gene summary),
  filtered to the requested transcript, with a compact top-tissues summary; correct
  the description.

### L-1 (LOW) `liftover_variant` bare `results:[]`
- Fix: add a `build_note` explaining no liftover mapping exists when results is
  empty (mirrors `compare_variant` build_notes).

### L-4 (LOW) Field-level response control
- Fix: add section/`include_*` projection to `get_gene_summary` (decouple
  "full ClinVar rows" from "full everything"); document token impact per flag.
- Follow-through (post-review): the finding also named `get_variant_details` and
  `get_gene_variants`, which still leaked the untrimmed population firehose while
  their sibling `get_variant_frequencies` trimmed it. Unify all three on one
  projector extracted to `population_shaping.py` (`project_variant_source`):
  drop subcohort / sex-split / zero-AC by default, additive toggles with
  back-compat to `get_variant_frequencies`, `response_mode='full'` (variant
  details) / `include_populations` (gene variants) as the escape hatches. Measured
  live: variant-details F508del 28.8 kB → 4.8 kB. Best-practice basis: Anthropic
  "Code execution with MCP" and StackOne token-optimization — filter before the
  model, lightweight-by-default with an opt-in detailed mode.

### L-2 (already fixed in code) heteroplasmy zero-bin trim
- The live container was stale; current-`main` `heteroplasmy.py` already trims and
  emits `truncated.kind=heteroplasmy_zeros`. Confirm on rebuild.

### L-6 (already shipped) gene-level carrier frequency
- `compute_gene_carrier_frequency` already added.

## Cross-cutting constraints
- 600-LOC hard cap (`make lint-loc`). `shaping.py` (575) is at its ceiling — new
  projection logic goes in `gene_summary_shaping.py` / new helpers, not `shaping.py`.
- Preserve MCP tool names + response schemas; new params are additive with
  backward-compatible defaults.
- Every new envelope field must survive `relax_output_schema` (additionalProperties).
- No ruff/mypy ignore widening. `make ci-local` green before handoff.
- Keep live calls out of default CI; live behavior validated via Docker rebuild + smoke.
