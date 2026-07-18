# gnomAD Link MCP -> 9.5/10: Correctness, Contract Consistency, and an Eval Harness — Design

> Historical record

Status: draft
Date: 2026-05-31
Owner: gnomAD Link MCP

## Motivation

Two fresh LLM-consumer reviews scored the server after the `F1-F6` and `G1-G10`
quality pushes had already landed:

- A consuming LLM rated it **~8.9/10** (response design 10, self-doc 10,
  discoverability 9; dinged token efficiency 8 for compact-but-not-minimal
  payloads and deferred-schema round-trips).
- A senior-tester pass over all 22 tools scored **~8.1/10** and surfaced one
  **HIGH correctness bug** plus five consistency/efficiency/doc nits.

This spec takes the server from "very good" to a measured **>=9.4/10** by (1)
fixing the one real correctness defect, (2) standing up the eval harness that
prior pushes never built so further gains are *measured not asserted*, and (3)
closing the residual contract-consistency and token-efficiency gaps that survive
from earlier rounds.

### Lineage (what is new vs residual)

- **HIGH bug is NEW, and is a direct miss from `F1`.** `F1` (commit bb86db9)
  fixed GRCh38<->GRCh37 direction handling in the **standalone** `liftover_variant`
  (`coordinates.py:75-79`, resolve-by-`reference_genome`). It did **not** update
  the **second, hand-rolled copy** inside `compare_variant_across_datasets`
  (`comparison.py:71`), which still hardcodes the wrong field. Phase 1 removes the
  duplication so the two paths cannot diverge again.
- **Contract-consistency work is RESIDUAL after `G5`.** `G5` added
  `_meta.next_commands` to several success paths (search_genes, liftover,
  get_region, specialty) but left `resolve_variant_id`/`search_variants` on a
  prose `next_steps` array and never added it to `get_variant_details`/
  `get_structural_variant`/`get_gene_variants`. Phase 3 finishes G5.
- **Eval harness is NET-NEW.** No prior plan (`F1-F6`, `G1-G10`, reliability,
  ergonomics) built an agentic tool-eval harness. This is the highest-leverage
  *process* gap and the gate for Phases 3-5.
- **`minimal` mode is NET-NEW** and additive on top of `G7`'s existing
  `compare` `compact` mode.

## Findings — independently re-verified against source (2026-05-31)

White-box confirmation (not just trusting the tester transcript); two of the
tester's findings were corrected:

| # | Sev | Verdict | Source-of-truth |
|---|-----|---------|-----------------|
| 1 | HIGH | **CONFIRMED + root-caused** | `comparison.py:71` reads `item["liftover"].variant_id` (always GRCh38) instead of resolving by build like `coordinates.py:75-79`. For the r2_1 (GRCh37) leg this echoes the GRCh38 input -> r2_1 queried with a GRCh38 coord -> 404 -> false `present:false`. **The existing test masks it**: `tests/unit/mcp/test_compare_variant.py` stubs the liftover record with `source`/`liftover` inverted vs the real API and vs `LiftoverResult` (`liftover_models.py`). |
| 2 | MED | **CORRECTED -> doc-only** | `compare` does **not** fan out concurrently: the dataset loop is sequential (`comparison.py:139-173`) and one `variant` query returns exome+genome together. The `rate_limited` came from N concurrent `compare` calls each making ~4 *sequential* upstream calls, saturating the 5-slot semaphore (`base_client.py:118-119`, `config.py:42`). Fix is a capabilities note, not code. |
| 3 | MED | **CONFIRMED (nuance)** | `resolve_variant_id`/`search_variants` emit prose `next_steps` (`search.py:258-262`, `:340-342`); `get_variant_details` (`variants.py:216-224`), `get_structural_variant` (`specialty.py:83`), `get_gene_variants` (`genes.py:187`) omit `next_commands` on success; `get_mitochondrial_variant`/`get_transcript_details` emit it only conditionally (`specialty.py:139-143`, `:199-203`). |
| 4 | LOW | **CONFIRMED** | `errors.py:146-147` returns `("search_genes", None)` -> `mcp_tool_error` renders `arguments: {}` (`:402-403`); `search_genes` requires `query`, so the fallback is not directly executable. |
| 5 | LOW | **CONFIRMED (nuance)** | SV (`sv_shaping.py:22-52`) and mito (`heteroplasmy.py:66-99`) *do* trim their histograms, but neither trims zero-AC or `_XX`/`_XY` sex-split population rows (no call into `population_shaping.filter_populations`). **Mito rows have no plain `ac` (only `ac_het`/`ac_hom`, `mitochondrial_models.py:12-14`)**, so SNV trimming cannot be reused as-is (Phase 4b). SV `rmi` is an upstream-native code, not a remap bug — there is no SV population-normalization layer. |
| 6 | LOW | **CONFIRMED** | `metadata.py:40` docstring says "Returns <2kB"; the payload's own `token_cost_hints` says "~7kB" (`resources.py:105`). The `~7kB` figure is accurate. |

Already-handled (no action): `READ_ONLY_OPEN_WORLD` tool annotations are set
(e.g. `comparison.py:85`), satisfying the Anthropic/MCP `readOnlyHint`/
`openWorldHint` guidance.

## Research grounding (Anthropic + Google)

Distilled from official sources (URLs below). The dimensions both vendors
converge on, and how this spec maps to them:

- **Anthropic — "Writing effective tools for agents"**: return only high-signal
  fields; consolidate multi-step ops; *evaluate tools with realistic multi-call
  tasks and iterate* (the explicit "prototype -> evaluate -> collaborate" loop).
  -> Phases 2 (eval harness), 4 (minimal mode).
- **Anthropic — "Define tools" / context engineering**: contract consistency;
  errors must be actionable and steer recovery (retry vs reformulate). -> Phases 3.
- **MCP spec (2025-11-25)**: tool-execution errors carry self-correctable
  feedback; provide `outputSchema` and conform; honest annotations. -> Phase 3.
- **Google — Gemini function-calling best practices**: keep the active tool set
  to **10-20**; specific high-level tools beat generic ones; structured error
  dicts with a human-readable message. **Hosted-MCP naming forbids `-`; use
  `snake_case` server names.** Streamable HTTP only (not SSE). -> Phase 5.
- **Google — ADK evaluation**: score both **trajectory** (which tools, what
  order: EXACT/IN_ORDER/ANY_ORDER) and **final-response quality**; probabilistic,
  not deterministic pass/fail. -> Phase 2 harness design.

Sources (verified 2026-05-31):

- https://www.anthropic.com/engineering/writing-tools-for-agents
- https://www.anthropic.com/engineering/code-execution-with-mcp
- https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools
- https://modelcontextprotocol.io/specification/2025-11-25/server/tools
- https://ai.google.dev/gemini-api/docs/function-calling
- https://ai.google.dev/gemini-api/docs/interactions (remote MCP: Streamable HTTP only; snake_case server names)
- https://google.github.io/adk-docs/evaluate/criteria/

## Design principles / invariants (carried from G1-G10)

- **Additive only.** New enum values, new `_meta` keys; never break a tool name
  or remove a response field. Deprecated fields (`next_steps`, `reference_genome`)
  remain one release with a deprecation note.
- **<=600 LOC per module.** New logic lands in new small modules; `shaping.py`
  (563) and `errors.py` (515) are near the cap and must not grow past it.
- **No live gnomAD calls in default CI.** Deterministic fixtures by default;
  live paths are `integration`-marked.
- **No new runtime dependencies; research-use scope only; no destructive tools.**
- **`make ci-local` green at every phase boundary.**

## Phase 1 — Fix the HIGH correctness bug (ship first)

**Goal:** `compare_variant_across_datasets` reports the truth for the GRCh37
`gnomad_r2_1` leg.

Changes:

1. **Extract one shared liftover-field resolver.** New tiny pure helper exported
   from `gnomad_link/mcp/tools/coordinates.py` (246 LOC, ample headroom):
   `resolve_target_variant_id(records, target_build) -> str | None` that iterates
   `("source", "liftover")` and returns the entry whose `reference_genome ==
   target_build`. This is the *existing correct logic* from `coordinates.py:75-79`,
   lifted to one place and imported by `comparison.py`.
2. **`coordinates.py`** standalone path calls the helper (behavior identical;
   guarded by existing liftover tests).
3. **`comparison.py:_resolve_r2_1_id`** calls the helper with
   `target_build="GRCh37"`, replacing the hardcoded `item["liftover"]` read.
4. **Correct the masking fixtures** in `tests/unit/mcp/test_compare_variant.py`
   so `source`=GRCh37 / `liftover`=GRCh38 matches `LiftoverResult` and the real
   API. Cross-check `test_liftover_build_note.py` (already uses correct
   semantics).

Tests:

- **Regression (deterministic, must fail before / pass after):** stub liftover
  with *correct* ordering; assert the r2_1 leg is `present:true` with the lifted
  GRCh37 id, and `build_note` carries an id **distinct from the GRCh38 input**.
- **Integration (`integration`-marked):** live `compare` of HFE C282Y
  `6-26092913-G-A` -> r2_1 `present:true` via `6-26093141-G-A` (exome AC ~8,344,
  AF ~0.033).

Acceptance: regression red->green; `make ci-local` green; live integration
confirms r2_1 presence.

## Success-envelope contract (referenced by Phases 2-4)

Defined here once so the harness's conformance dimension and Phase 3 have a
single source of truth. Today every success/error envelope is merged with
`_provenance_meta` in `run_mcp_tool` (`errors.py:484-491`); the canonical
**success** envelope after this work is:

- **Top level:** the tool-specific payload, plus a `headline: str` on every
  headline tool (see Phase 4 table). `success` is implicit (no `error` key).
- **`_meta` (always present):**
  - `unsafe_for_clinical_use: true` (`_BASE_META`, `errors.py:43-46`)
  - `gnomad_release: <GNOMAD_DATA_RELEASE>`
  - `dataset` + `reference_genome` when the call is dataset-scoped
    (`_DATASET_BUILD`, `errors.py:100-106`)
  - `clinvar_release_date: str | null` (nullable; from `clinvar_date_cache`)
  - `next_commands: [{tool, arguments}]` — **structured, non-empty, executable**
    (Phase 3 makes this universal on success; `arguments` must be directly
    callable, never `{}`)
- **Truncation (when rows dropped):** a `truncated` (or `truncated_payload`)
  block naming what was dropped and a `to_restore` hint (e.g.
  `response_mode='compact'`/`'full'` or the specific include_* toggle).
- **Deprecated fields** (`next_steps`, `reference_genome` param echo) may appear
  for one release, each carrying a `_meta.deprecated_*` note.

The harness's **envelope-conformance** dimension asserts this contract per tool.

## Phase 2 — Eval harness + baseline scorecard (the gate)

**Goal:** score the server the way the LLM reviewers did, so Phases 3-5 show
measured deltas. **Two distinct harnesses** (they are not the same tool):

### 2a. Deterministic CI eval (the gate; wired into `ci-local`)

- Layout: **`tests/eval/`** (under the single `tests/` root per AGENTS.md).
- Scripted, in-process MCP tool calls against **recorded fixtures using
  `respx`** (already a dev dependency, `pyproject.toml:52`) plus canned JSON.
  **No new dependency** — do not introduce `vcrpy`/cassettes.
- Scores three deterministic dimensions per scenario:
  1. **Trajectory** — the expected tool set/order (EXACT / IN_ORDER / ANY_ORDER)
     for a scripted call sequence.
  2. **Token cost** — measured serialized payload bytes per call/scenario (the
     metric Phase 4 must move).
  3. **Envelope conformance** — asserts the Success-envelope contract above
     (`headline` present where promised, structured non-empty `next_commands`,
     provenance + `unsafe_for_clinical_use`).
- Emits a **scorecard report** (per-dimension + total) and commits a baseline
  snapshot.
- **Wiring:** add a fast `make eval-ci` target and add it to the `ci-local`
  target (currently `format-check lint-ci lint-loc typecheck-fast test-fast`),
  since it is the Phase 3-5 gate. Must stay fast (fixture replay, no network).

### 2b. Agentic eval (optional; manual / `integration`)

- A real-model agent loop (LLM + tool calls) over the scenarios, scoring
  **final-answer quality** (LLM-as-judge / rubric, per Google ADK
  `final_response_match`) and **live trajectory**. Replays against the real
  gnomAD + ClinVar API.
- **Never in default CI** — `integration`-marked / `make eval-live`; run for
  release validation only. Requires model credentials, so it is opt-in.

Scenarios (both harnesses), realistic and grounded in known biology:

- Carrier frequency for **HFE** (gene-level summation path).
- Compare **C282Y** across r4/r3/r2_1 (covers the Phase-1 fix).
- Retrieve **research evidence (ClinVar + gnomAD context) for m.3243A>G**
  (mito tool) — evidence retrieval, **not** a clinical/pathogenicity verdict.
- **G6PD V68M** XL carrier rate (afr female-carrier ~0.262 / affected-male ~0.130).
- **GRIN2B** LoF count (`stop_gained` filter vs `obs_lof`).

The 8 reviewer dimensions map onto the Anthropic-10 / Google-14 rubrics; 2a
produces the *true deterministic* baseline (prior ~8.1-8.9 are qualitative).

Acceptance: `make eval-ci` runs deterministically inside `ci-local` and emits a
baseline scorecard; `make eval-live` validated once against gnomAD.

## Phase 3 — Contract consistency (finish G5)

**Goal:** one envelope contract — structured `_meta.next_commands` on every
success and executable fallback args on every error.

Changes:

1. New small `gnomad_link/mcp/next_commands.py` with typed builder helpers so
   every tool constructs `next_commands` identically.
2. **Convert** `resolve_variant_id` + `search_variants` prose `next_steps` ->
   structured `_meta.next_commands` (top hit -> `get_variant_frequencies`); keep
   `next_steps` as a **deprecated** field one release (additive, non-breaking).
3. **Add** `next_commands` to `get_variant_details` (-> `get_clinvar_variant_details`
   / `compare_variant_across_datasets`), `get_structural_variant`, and
   `get_gene_variants`; make `get_mitochondrial_variant` / `get_transcript_details`
   emit it **unconditionally** (sensible default chain when gene context absent).
4. **Executable error fallbacks:** add `query: str | None` to `McpErrorContext`
   (`errors.py:53-63`); populate it in `resolve_variant_id`/`search_variants`;
   change `_fallback_for` (`errors.py:146-147`) to return
   `("search_genes", {"query": context.query})` when present.
5. Update the capabilities contract text so the "`next_commands` on success and
   error" claim is true (`resources.py:226-230`).

Tests: per-tool envelope-shape assertions; the harness's **envelope-conformance**
dimension goes to 100%.

## Phase 4 — Token efficiency (measured against Phase 2)

**Goal:** a genuinely minimal mode for top-line questions, and SV/mito compact
parity with SNV trimming. All additive; default behavior unchanged.

### 4a. `response_mode='minimal'` — per-tool, not generic

Correction to the original draft: `get_variant_frequencies` (`variants.py:48`)
currently has **no** `response_mode` param (the one at `:163` belongs to
`get_variant_details`), and "global AC/AN/AF/popmax" does **not** map to gene
tools (genes have no AF). So `minimal` is defined **per tool**, reading each
tool's existing headline-source fields. `get_variant_details` is **excluded**
(it is the deliberately-detailed tool; its own docstring already steers
allele-count-only callers to `get_variant_frequencies`).

| Tool | `response_mode` today | `minimal` returns (+ `_meta`) | omits | restore |
|------|----------------------|-------------------------------|-------|---------|
| `get_variant_frequencies` | **none -> add** `compact\|full\|minimal` (default `compact` = today's behavior) | `headline` + `summary{overall_af, max_pop, max_pop_af}` + `major_consequence` | exome/genome per-pop arrays | `response_mode='compact'` |
| `compute_carrier_frequency` | `compact\|full` -> +`minimal` | `headline` + `global{carrier_rate, affected_rate, Wilson CI}` + inheritance | per-population rows, full citations | `response_mode='compact'` |
| `compute_gene_carrier_frequency` | `compact\|full` -> +`minimal` | `headline` + `global{carrier_one_in,...}` + `contributing_variants.count` | per-population rows, contributing-variant list | `response_mode='compact'` |
| `get_gene_details` | `compact\|full` -> +`minimal` | `headline` + `symbol`/`gene_id` + `gnomad_constraint{pli, oe_lof}` + coords | transcripts, full constraint matrix | `response_mode='compact'` |
| `get_gene_summary` | `compact\|full` -> +`minimal` | `headline` + top-line constraint + variant/ClinVar counts | per-category breakdowns | `response_mode='compact'` |
| `compare_variant_across_datasets` | `compact\|full` -> +`minimal` | `headline` + per-dataset `present` + global AF per dataset | `per_population_af_deltas` detail, raw rows | `response_mode='compact'` |

Every `minimal` payload keeps the full `_meta` block (provenance + non-empty
`next_commands`) and the inline research-use safety flag — minimal must not drop
the groundability guardrail. Implemented in a **new**
`gnomad_link/mcp/minimal_shaping.py` so `shaping.py` (563 LOC) stays under cap.

### 4b. SV/mito compact trimming — domain-specific helpers (do NOT reuse SNV `filter_populations`)

SNV `population_shaping.filter_populations` keys on `ac`, but the row shapes
differ, so naive reuse is wrong:

- **Mito** rows (`mitochondrial_models.py:12-14`) have **no `ac`** — only `an`,
  `ac_het`, `ac_hom`. A new `mito` projection treats a row as empty only when
  `ac_het == 0 and ac_hom == 0`; it also drops `_XX`/`_XY` sex-split rows and
  all-zero haplogroup rows. (`population_shaping.is_sex_split` is reusable for
  the sex-split test only.)
- **SV** rows (`structural_variant_models.py`) have `ac`/`an` plus
  `homozygote_count`/`hemizygote_count`. A new `sv` projection drops zero-`ac`
  and `_XX`/`_XY` rows **while preserving** hom/hemi counts on kept rows.

Both emit a `truncated` block and corrected `token_cost_hints`. `rmi` (SV
population code) is **upstream-native**: document it in capabilities; do **not**
silently remap to `remaining` (optional explicit map is future-only).

Tests: per-tool `minimal` shape assertions; SV and mito trimming assertions
(including the mito `ac_het`/`ac_hom` zero rule); the harness's **token-cost**
dimension shows a measured reduction for top-line scenarios.

## Phase 5 — Docs + Gemini interop (polish)

Changes:

1. `metadata.py:40` docstring "Returns <2kB" -> "Returns ~7kB" (match
   `resources.py:105`).
2. `resources.py` concurrency note: state that `compare_variant_across_datasets`
   issues **~4 sequential** upstream calls per invocation, so N concurrent
   `compare` calls consume N slots continuously (corrects the prior "fan-out"
   theory; complements the existing `internal_fanout` note for
   `compute_gene_carrier_frequency`).
3. **Gemini interop (docs-first).** The remote-MCP server **name is supplied by
   the Gemini client request/config**, so the server cannot "provide an alias"
   itself. Action is documentation in the MCP connection guide: show a
   `name: "gnomad_link"` (snake_case) example for hosted-MCP clients that reject
   `-`, note Streamable-HTTP-only (the server already serves MCP HTTP), and add
   an **`allowed_tools` example** that selects a focused sub-set so a Gemini
   agent's active tool set stays within the 10-20 guidance instead of relying on
   client-side ToolSearch.
4. **README + docs tool-count refresh.** `README.md:20` still says "15 MCP
   Tools" while capabilities and this spec say 22. Update `README.md` (count +
   the "Available MCP Tools" table at `:139`) and the MCP connection guide to
   the current inventory. Document the tool categories and that
   deferred-loading/tool-search mitigates the 22-vs-10-20 gap. **Explicit
   non-goal** to consolidate/rename tools now — renames break the stable-name
   contract.

## Definition of "9.5" (measured, not asserted)

Pass the milestone when the Phase-2 harness reports:

- Phase-1 **compare-bug correctness = pass** (r2_1 leg present for C282Y).
- **Envelope-conformance dimension = 100%** across all scored tools.
- A **measured token reduction** on top-line scenarios from `minimal` mode.
- **Zero regressions** vs the committed baseline scorecard.
- Total **>= 9.4/10**, `make ci-local` green.

## Non-goals

- No tool renames or removals; no clinical-decision-support features; no new
  destructive tools; no broadened Ruff/mypy ignores.
- No re-ranking fix for the `GRIN`-prefix gene-search omission (upstream gnomAD
  autocomplete limitation; already documented in `F4`).
- No tool-count consolidation (future consideration only).

## Risks / open questions

- **Fixture fidelity (Phase 2):** recorded `respx` fixtures can drift from live
  gnomAD. Mitigation: a schema-drift check already exists
  (`get_gnomad_diagnostics`); `make eval-live` (2b) re-validates before release.
- **`minimal` mode surface (Phase 4):** must not let "minimal" drop the
  groundability guardrail — the research-use safety flag and short citation
  pointer stay inline (consistent with the ergonomics spec's guardrail).
- **`shaping.py` headroom:** at 563/600; Phase 4 must not push it over — hence
  the new `minimal_shaping.py`.
