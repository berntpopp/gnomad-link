# MCP 9.5 Eval Baseline -- 2026-05-31

**Purpose:** Phase-2 deterministic baseline that gates Phases 3-5.
Values are measured by the harness, not asserted by hand.

## Aggregate Dimensions

| Dimension             | Score     | Max  | Notes                                      |
|-----------------------|-----------|------|--------------------------------------------|
| trajectory            | 10.000000 | 10.0 | All 5 scenarios followed expected call order |
| token_cost            | 10.000000 | 10.0 | All serialized payloads within byte budgets  |
| envelope_conformance  |  9.266667 | 10.0 | See "Known sub-10" below                   |
| **total**             |  **9.755556** | **10.0** |                                    |

## Per-Scenario Byte Budget

Each value is the measured serialized response size in bytes from `baseline.json`.
Multiple values indicate a multi-call scenario (one entry per call).

| Scenario                                     | Tool call(s)                                              | Measured bytes      |
|----------------------------------------------|-----------------------------------------------------------|---------------------|
| gene_carrier_frequency_hfe                   | compute_gene_carrier_frequency                            | 2049                |
| compare_variant_across_datasets_r4_r2_1      | compare_variant_across_datasets                           | 2221                |
| gene_variants_stop_gained                    | get_gene_variants                                         | 1531                |
| resolve_then_xl_carrier_frequency            | resolve_variant_id, compute_carrier_frequency             | 413, 1351           |
| variant_clinical_evidence                    | get_mitochondrial_variant, get_clinvar_variant_details    | 715, 1524           |

## Known sub-10: envelope_conformance

`envelope_conformance` is 9.267 rather than 10.0 because `resolve_variant_id`
and `get_gene_variants` currently emit no `next_commands` suggestions on the
success path. Phase 3 is expected to add guidance signals to these tools and
raise the score toward 10.0.

## Mapping to Prior Qualitative Scores

Previous manual reviews produced two qualitative scores:

- Consuming LLM judge: ~8.9 / 10 across 22 tools
- Senior-tester review: ~8.1 / 10 across 22 tools

Those scores were subjective, non-deterministic, and covered the full tool
surface. This harness measures five representative multi-step scenarios on
three objective dimensions (trajectory correctness, token economy, envelope
conformance). The prior scores are not directly comparable to these numbers;
this harness now produces the true, reproducible baseline against which
Phases 3-5 improvements will be measured.

## How to Refresh

Re-write `baseline.json` intentionally after a planned improvement:

```
EVAL_UPDATE_BASELINE=1 uv run pytest tests/eval
```

Run the deterministic harness in CI (no network required):

```
make eval-ci
```
