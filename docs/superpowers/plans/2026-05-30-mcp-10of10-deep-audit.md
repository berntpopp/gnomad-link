# MCP 10/10 Deep Audit — Execution Plan

Source: research-backed multi-agent audit (workflow `wkw6p12ov`, 72 agents):
4 best-practice research agents -> 10 dimension reviewers -> adversarial
verification of every finding -> synthesis. 56 findings confirmed real and not
already handled (1 dropped), deduped into 16 ranked, contract-safe fixes.

Honest pre-fix score: **7.6/10**. Per-dimension: discoverability 8, input_schema
8, output_structure 8, self_doc_guardrails 8, error_handling 7, naming 8,
token_efficiency 8, concurrency_speed 7, data_fidelity 6, mcp_conformance 8.

Invariants for every fix: additive only; no tool-name/response-schema break
(schemas are relaxed `additionalProperties:true`); <=600 LOC/module; no new
dependencies; no live gnomAD calls in default CI; research-use scope only.

## Fix groups (commit boundaries)

- [x] **G1 data-fidelity / ClinVar correctness (#1)** — `conflicting` short-circuit
  in `shaping._classify_clinical_significance` + new `conflicting` counts key;
  `gene_summary_shaping._is_pathogenic` excludes conflicting. Matches the
  already-correct `gene_carrier_filters` path. Visible numeric correction.
- [x] **G2 errors.py cluster (#5,#6,#14,#16, error_handling-1/-2)** — envelope
  `next_commands` from classified fallback; `ToolInputError(ValueError)` so
  hand-authored guards surface; tool-aware not_found recovery prose; symmetric
  `success` flag; truthful rate_limited prose; build_mismatch key
  `reference_genome`->`source_genome`; mito `_fallback_for` branch.
- [x] **G3 ClinVar date in _meta (#7)** — leaf `clinvar_date_cache.py` to break the
  metadata->errors cycle; merge nullable `clinvar_release_date` into `_BASE_META`;
  capabilities resource reads the cache.
- [x] **G4 capabilities discovery enrichment (#9,#3-doc,#13-static)** — add
  `prompts`, `truncation_contract`, `field_glossary`, `error_taxonomy`,
  `parameter_conventions`, carrier `recommended_workflows`, `next_commands` doc
  in cheatsheet/response_fields, concurrency `queue_wait_seconds`/fanout note;
  one facade.py instructions bullet.
- [x] **G5 next_commands emission on success paths (#3-emit)** —
  search_genes->get_gene_details, liftover->get_variant_frequencies(target),
  get_region->get_gene_variants/get_clinvar_variant_details, specialty tools.
- [x] **G6 output structure (#10)** — headline builders for the 6 headline-less
  tools; `has_clinvar` self-describing sentinel; normalize region_span truncation
  block. (af_source labels #2 moved to G10.)
- [x] **G7 token efficiency (#8)** — compare_variant compact `response_mode`
  (drop redundant per-dataset populations[]); delete duplicate `sources` key in
  gene_carrier_shaping.
- [x] **G8 input schema + patterns (#11,#12)** — clinvar variant_id pattern,
  sv_type Literal (non-breaking via case-normalizing), transcript_id pattern,
  compare datasets list[Literal], bare-Field descriptions, prompts consequence
  example; shared `patterns.py`; per-call queue-wait deadline in base_client.
- [ ] **G9 mcp conformance (#13 safe subset)** — get_server_capabilities
  open-world annotation; resource `mime_type`/`name`; MCP_PROTOCOL_VERSION from
  SDK; prompt-arg patterns. (Skip fragile private-attr listChanged suppression.)
- [ ] **G10 remaining data-fidelity / self-doc (#15,#4,#2)** — variant_carrier
  headline research-use caveat; transcript pext_note; gene-carrier
  omitted_populations + AR affected CIs + AD per-pop key fix + length-weighted
  mean_pext; ClinVar fan-out backpressure accounting.

## Verification
- `make test` after each group; `make ci-local` before handoff.
- Do NOT push (standing rule: no merge/push to main without go-ahead).
