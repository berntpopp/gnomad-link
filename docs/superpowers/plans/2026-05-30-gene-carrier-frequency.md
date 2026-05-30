# Gene-Level Carrier Frequency — Implementation Plan

Spec: `docs/superpowers/specs/2026-05-30-gene-carrier-frequency-design.md`
Reference impl: `../gnomad-carrier-frequency` (CLI ground truth: `gnomad-cf query CFTR` → global ≈ 1:18).

TDD throughout. `make ci-local` green per task. Atomic `feat(mcp):` commits. Live validation against the sibling CLI numbers.

## Tasks

- [ ] **T1 — Enriched GraphQL + client.** Create `gene_carrier_variants.graphql` (gene.variants enriched: transcript_consequence{is_canonical,lof,consequence_terms,major_consequence}, exome/genome{ac,an,homozygote_count,filters,populations{id,ac,an,homozygote_count}}, flags; + clinvar_variants{variant_id,clinical_significance,review_status,gold_stars}). Client `get_gene_carrier_variants(gene_id|gene_symbol, dataset)`; client `get_clinvar_submissions(variant_id, reference_genome)` (reuse clinvar_variant). Query-loads test.

- [ ] **T2 — Pure math `gene_carrier_math.py`.** `effective_af`, `variant_carrier_rate` (reuse carrier_math), `gene_carrier_rate` (GCR=1−∏(1−VCR)), `hwe_carrier` (2pq), `simplified_carrier` (2·ΣAF), `hwe_expected_hom`, `aggregate_population` (sumAF,totalAC,maxAN,VCRs→carrier per method, genetic_prev=q², bayesian=q²·pen). Golden tests (match sibling formulas).

- [ ] **T3 — Filters `gene_carrier_filters.py`.** `is_hc_lof`, `is_missense`, `is_pathogenic_clinvar(threshold)`, `is_conflicting`, `meets_conflicting_threshold(submissions, pct)`, `qualifies(variant, clinvar, config)`, quality flags (high_af, high_hom, gnomad_filtered, genomes_only). Unit tests against the sibling's decision tree.

- [ ] **T4 — `GeneCarrierService`.** Orchestrate: fetch → join clinvar → (opt) fetch conflicting submissions → filter+quality → per-pop+global aggregate. Population sets per version. Thin FrequencyService delegate. Service tests (mocked client, golden end-to-end on a small fixture).

- [ ] **T5 — `gene_carrier_shaping.py`.** Compact `{gene,dataset,settings,global,populations[],contributing_variants{count,top,truncated?},qualifying_sources,assumptions_note,citations}`; sort pops by carrier desc; cap top variants. Shaping tests.

- [ ] **T6 — `compute_gene_carrier_frequency` tool + wiring.** `register_gene_carrier_tools`; all params/defaults per spec; relax_output_schema; READ_ONLY_OPEN_WORLD; run_mcp_tool; next_commands. Wire __init__, resources.py (tools+token_cost_hints≤80+tool_categories["gene"]), EXPECTED_TOOLS. Tool tests + parity.

- [ ] **T7 — Live validation + integration test.** `integration`-marked test: CFTR gnomad_r4 default → global carrier ≈ 0.0568 (±tolerance), NFE ≈ 0.063. Rebuild Docker, smoke-test the tool live and confirm it matches `gnomad-cf query CFTR`.

## Done criteria
21 → 22 tools; ci-local green; parity gate green; every module <600 LOC; CFTR default reproduces sibling CLI numbers live (global ~1:18); all toggles functional; safety meta present.
