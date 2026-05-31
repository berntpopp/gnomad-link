# MCP 9.5 Eval Baseline -- 2026-05-31

**Purpose:** Deterministic baseline that gates Phases 3-5.
Values are measured by the harness, not asserted by hand.

This document now records both the Phase 2 (initial) numbers and the
Phase 3 (post) improved numbers so the before/after is visible.

## Aggregate Dimensions

### Phase 2 (initial baseline, pre-Phase 3)

| Dimension             | Score     | Max  | Notes                                        |
|-----------------------|-----------|------|----------------------------------------------|
| trajectory            | 10.000000 | 10.0 | All 5 scenarios followed expected call order |
| token_cost            | 10.000000 | 10.0 | All serialized payloads within byte budgets  |
| envelope_conformance  |  9.266667 | 10.0 | resolve_variant_id / get_gene_variants had no next_commands |
| **total**             |  **9.755556** | **10.0** |                                          |

### Phase 3 (post -- current baseline.json)

| Dimension             | Score      | Max  | Notes                                        |
|-----------------------|------------|------|----------------------------------------------|
| trajectory            | 10.000000  | 10.0 | All 5 scenarios followed expected call order |
| token_cost            | 10.000000  | 10.0 | All serialized payloads within byte budgets  |
| envelope_conformance  | 10.000000  | 10.0 | Universal next_commands on every tool        |
| **total**             | **10.000000** | **10.0** |                                          |

## Per-Scenario Byte Budget

Each value is the measured serialized response size in bytes from `baseline.json`.
Multiple values indicate a multi-call scenario (one entry per call).

### Phase 2 (initial)

| Scenario                                     | Tool call(s)                                              | Measured bytes      |
|----------------------------------------------|-----------------------------------------------------------|---------------------|
| gene_carrier_frequency_hfe                   | compute_gene_carrier_frequency                            | 2049                |
| compare_variant_across_datasets_r4_r2_1      | compare_variant_across_datasets                           | 2221                |
| gene_variants_stop_gained                    | get_gene_variants                                         | 1531                |
| resolve_then_xl_carrier_frequency            | resolve_variant_id, compute_carrier_frequency             | 413, 1351           |
| variant_clinical_evidence                    | get_mitochondrial_variant, get_clinvar_variant_details    | 715, 1524           |

### Phase 3 (post -- current baseline.json)

| Scenario                                     | Tool call(s)                                              | Measured bytes      |
|----------------------------------------------|-----------------------------------------------------------|---------------------|
| gene_carrier_frequency_hfe                   | compute_gene_carrier_frequency                            | 2049                |
| compare_variant_across_datasets_r4_r2_1      | compare_variant_across_datasets                           | 2221                |
| gene_variants_stop_gained                    | get_gene_variants                                         | 1707 (+176)         |
| resolve_then_xl_carrier_frequency            | resolve_variant_id, compute_carrier_frequency             | 630 (+217), 1351    |
| variant_clinical_evidence                    | get_mitochondrial_variant, get_clinvar_variant_details    | 715, 1524           |

The two byte increases (+217 bytes on resolve_variant_id, +176 bytes on
get_gene_variants) are the added structured next_commands JSON. This is an
intended, reviewed token cost that pays for full groundability: every tool
now carries a ready-to-call next step so the consuming LLM never has to guess.

### Phase 4a (response_mode='minimal' scenarios)

Two minimal-mode scenarios were added; they reuse the existing gene_carrier
and compare stubs and prove the projection's measured reduction. All existing
budgets are unchanged and all dimensions stay 10.0 (minimal keeps headline +
_meta + non-empty next_commands, so envelope conformance is preserved).

| Scenario                                     | Tool call(s)                                              | Measured bytes      |
|----------------------------------------------|-----------------------------------------------------------|---------------------|
| gene_carrier_frequency_hfe_minimal           | compute_gene_carrier_frequency (minimal)                  | 1076 (compact 2049) |
| compare_variant_across_datasets_minimal      | compare_variant_across_datasets (minimal)                 | 934  (compact 2221) |

Each minimal scenario's byte budget is smaller than its compact counterpart:
gene carrier 1076 vs 2049 (-47.5%), compare 934 vs 2221 (-57.9%).

## Phase 3 Result

Phase 3 added structured `_meta.next_commands` ({tool, arguments} entries) to
every tool's success and error envelope:

- `resolve_variant_id` and `search_variants` (deprecated alias) converted from
  the prose `next_steps` array to structured next_commands; `next_steps` is
  retained as a deprecated field for one release.
- `get_gene_variants` gained next_commands on its success path.
- `get_mitochondrial_variant` and `get_transcript_details` made next_commands
  unconditional (previously emitted only on some code paths).
- `get_variant_details` and structural variant tools (`get_structural_variant`,
  `search_structural_variants`) gained next_commands on success and error paths.

Net effect: `envelope_conformance` 9.266667 -> 10.0, `total` 9.755556 -> 10.0.

## Mapping to Prior Qualitative Scores

Previous manual reviews produced two qualitative scores:

- Consuming LLM judge: ~8.9 / 10 across 22 tools
- Senior-tester review: ~8.1 / 10 across 22 tools

Those scores were subjective, non-deterministic, and covered the full tool
surface. This harness measures five representative multi-step scenarios on
three objective dimensions (trajectory correctness, token economy, envelope
conformance). The prior scores are not directly comparable to these numbers;
this harness now produces the true, reproducible baseline against which
Phases 4-5 improvements will be measured.

## Final Milestone Scorecard (post Phase 5)

### Aggregate dimensions -- final

| Dimension             | Score      | Max  | Notes                                              |
|-----------------------|------------|------|----------------------------------------------------|
| trajectory            | 10.000000  | 10.0 | All 7 scenarios followed expected call order       |
| token_cost            | 10.000000  | 10.0 | All serialized payloads within byte budgets        |
| envelope_conformance  | 10.000000  | 10.0 | Universal next_commands preserved through Phase 5  |
| **total**             | **10.000000** | **10.0** |                                                |

Source: `tests/eval/baseline.json` (7 scenarios, 9 measured-bytes entries).

### Before / after summary

| Milestone point       | envelope_conformance | total     |
|-----------------------|----------------------|-----------|
| Phase 2 initial       | 9.266667             | 9.755556  |
| Phase 3 (post)        | 10.000000            | 10.000000 |
| Phase 5 / final       | 10.000000            | 10.000000 |

Phase 2 added the harness and captured the initial gap (two tools lacked
next_commands). Phase 3 closed the conformance gap. Phases 4-5 added the
compare-bug fix, minimal-mode projections, and SV/mito compact trimming
without disturbing any scored dimension.

### Per-scenario measured bytes -- final (from baseline.json)

| Scenario                                     | Tool call(s)                                           | Bytes           |
|----------------------------------------------|--------------------------------------------------------|-----------------|
| gene_carrier_frequency_hfe                   | compute_gene_carrier_frequency                         | 2049            |
| gene_carrier_frequency_hfe_minimal           | compute_gene_carrier_frequency (minimal)               | 1076            |
| compare_variant_across_datasets_r4_r2_1      | compare_variant_across_datasets                        | 2221            |
| compare_variant_across_datasets_minimal      | compare_variant_across_datasets (minimal)              | 934             |
| gene_variants_stop_gained                    | get_gene_variants                                      | 1707            |
| resolve_then_xl_carrier_frequency            | resolve_variant_id, compute_carrier_frequency          | 630, 1351       |
| variant_clinical_evidence                    | get_mitochondrial_variant, get_clinvar_variant_details | 738, 1524       |

### Token-reduction evidence

Minimal-mode scenarios (eval harness, `tests/eval/scenarios.py`):

- gene_carrier compact 2049 B -> minimal 1076 B: -47.5%
- compare compact 2221 B -> minimal 934 B: -57.9%

SV compact-population-trim (`test_compact_population_trim_reduces_serialized_bytes`
in `tests/unit/mcp/test_sv_single_shaping.py`): realistic 28-row population
payload, full=2429 B, compact=374 B, -84.6%.

Mito compact-trim (`test_compact_byte_reduction` in
`tests/unit/mcp/test_mt_heteroplasmy_trim.py`): 10-population + 10-haplogroup
realistic payload, full=1728 B, compact=463 B, -73.2%.

All four reductions are asserted by deterministic unit or eval tests; no
network access required.

### 9.5 Milestone checklist

1. PASS  Compare-bug correctness -- gnomad_r2_1 leg resolves for C282Y.
   Eval scenario `compare_variant_across_datasets_r4_r2_1` (tests/eval/scenarios.py
   line ~87 _check_compare) asserts present=True for both r4 and r2_1 legs AND
   lifted_variant_id == "6-26093141-G-A". All 8 eval tests pass (make eval-ci,
   uv run pytest tests/eval -q). Live guard: tests/integration/
   test_mcp_live_tools.py::test_compare_finds_hfe_c282y_in_r2_1_live.

2. PASS  Envelope conformance = 100% -- envelope_conformance == 10.0 in
   baseline.json; all 7 scenarios pass the conformance check.

3. PASS  Measured token reduction -- minimal-mode: gene_carrier -47.5%,
   compare -57.9% (eval harness). SV compact trim: -84.6%
   (test_sv_single_shaping.py). Mito compact trim: -73.2%
   (test_mt_heteroplasmy_trim.py).

4. PASS  Zero regressions -- all dimensions 10.0; no dimension below the
   Phase-2 baseline (trajectory was already 10.0; token_cost was already 10.0;
   envelope_conformance improved from 9.266667 to 10.0). uv run pytest tests/eval
   -q passes without failures.

5. PASS  Total >= 9.4 -- total == 10.0 in baseline.json.

## How to Refresh

Re-write `baseline.json` intentionally after a planned improvement:

```
EVAL_UPDATE_BASELINE=1 uv run pytest tests/eval
```

Run the deterministic harness in CI (no network required):

```
make eval-ci
```
