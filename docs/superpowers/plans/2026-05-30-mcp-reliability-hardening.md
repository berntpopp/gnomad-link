# MCP Reliability Hardening — Execution Plan

Date: 2026-05-30
Spec: `docs/superpowers/specs/2026-05-30-mcp-reliability-hardening-design.md`

Order: P0 (correctness/availability) → P1 (guidance/output correctness) →
P2 (token efficiency) → findings outside the research punch-list (M-4, L-1) →
verification. TDD per task; atomic commit per task; `make ci-local` at the end.

## P0

- [x] **H-1** unwrap `get_variant_details` + not_found guard + regression test. (351b918)
  - Follow-up: `in_silico_predictors` is a list, not a dict — latent schema mismatch
    the bug had masked, caught by live smoke and fixed.
- [x] **M-3a** persistent reconnecting session + lazy double-checked lock + semaphore
  (`GNOMAD_MAX_CONCURRENCY`) + dependency-free jittered retry on retryable transport
  codes; idempotent `close()`. New base_client seam tests (concurrency/retry/429). (bd10b56)
- [x] **M-3b** FastAPI lifespan teardown closes the service. (bd10b56)
- [x] **M-2a** `UpstreamInputError` + `RateLimitedError` classified at the boundary. (bd10b56)

## P1

- [x] **M-2b** `invalid_input` + `rate_limited` codes; context-aware fallback +
  action-typed `recovery_action`. (M-2 commit)
- [x] **M-1a** `schema_relax` nullable-izes bare scalars (skip enum/const/containers).
- [x] **M-1b** SV model `pos/end/ac/an/af` Optional; `cpx_intervals` is list[str]
  (caught live). (M-1 commits)

## P2

- [x] **M-1c / L-3** `shape_structural_variant` trims histograms + dedupes the flat
  gene list; `get_structural_variant` gains `response_mode`. Live-verified on CPX/BND/INV.
- [x] **L-4** `gene_summary` section/`include_*` projection (decouple full-ClinVar).
- [x] **Token hints** converted to parameter-anchored ranges.

## Findings outside the research punch-list

- [x] **M-4** `get_transcript_details`: TranscriptService unwrap + best-effort GTEx
  top-tissues via the gene path. Live-verified (liver top tissue).
- [x] **L-1** `liftover_variant` `build_note` on empty mapping. Live-verified.
- [x] **L-2** heteroplasmy zero-bin trim never fired on real N+1 histograms; fixed.
  Live-verified (106 bins dropped).

## L-4 follow-through (post-review) — population shaping unified

The first pass shipped L-4 for `get_gene_summary` only. A re-review found the same
untrimmed-population firehose still live in the other two tools the finding named:

- `get_variant_details` compact never trimmed `exome`/`genome` populations — F508del
  returned the full 28.8 kB payload under the advertised "compact ~3 kB" (200+
  HGDP/1kg/sex-split/zero-AC rows).
- `get_gene_variants` passed every variant's full per-population breakdown through raw.

Fix (cohesive split, mirrors the `get_variant_frequencies` defaults):

- [x] Extract the population projector into `gnomad_link/mcp/population_shaping.py`
  (`filter_populations`, `build_populations_truncated`, `project_variant_source`,
  `population_projection_note`). Drops `shaping.py` 575 → 555, off its LOC ceiling.
- [x] `shape_variant_details_compact` trims exome/genome populations + adds
  `populations`/`include_subcohorts`/`include_sex_split`/`exclude_zero_populations`
  toggles; per-source `truncated.kind == "populations"`. **Live: 28.8 kB → 4.8 kB (83%).**
- [x] `shape_gene_variants` trims each variant's populations + `include_populations`
  scan mode; one payload-level `population_projection` note (not per-row blocks).
  **Live: include_populations=False ~30% leaner.**
- [x] Token hints corrected in tool docstrings + `resources.py`; limitations note
  widened to all three variant-bearing tools.
- [x] TDD: 16 new unit tests (shaping + SDK-handler wiring/output-schema) + 3 live
  integration assertions. `make ci-local` green (format, lint, lint-loc, mypy, 393 tests).

## Verification

- [x] `resources.py` token hints updated; capabilities parity green.
- [x] `make ci-local` green (format, lint, lint-loc, mypy, 393 tests).
- [x] Docker rebuilt; live-smoked every fixed tool incl. CPX/BND/INV, BRCA2→invalid_input,
  transcript GTEx, liftover note, heteroplasmy trim.
- [x] Live integration test for M-3 concurrency (12 concurrent real-API calls, no race).
- [x] Live integration: variant-details + gene-variants population trimming verified
  against gnomAD r4 (in-process, new code).
- [ ] Present finishing-a-development-branch options (no merge/push without go-ahead).
