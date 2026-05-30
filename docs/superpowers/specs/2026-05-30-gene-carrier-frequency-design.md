# Gene-Level Carrier Frequency — Design Spec

Status: approved (full parity), 2026-05-30
Pairs with plan: `docs/superpowers/plans/2026-05-30-gene-carrier-frequency.md`

## Goal

Add a NEW MCP tool `compute_gene_carrier_frequency` that computes autosomal-recessive
carrier frequency for a whole GENE by summing qualifying pathogenic variants —
faithfully porting the validated algorithm from the sibling project
`../gnomad-carrier-frequency` (berntpopp), with the SAME setting defaults and
possibilities. The existing single-variant `compute_carrier_frequency` stays
unchanged. Acceptance: CFTR (gnomad_r4) global ≈ 1 in 18 (5.68%), NFE ≈ 1 in 16,
matching the sibling CLI `gnomad-cf query CFTR`.

This is research-use only; not clinical decision support.

## Algorithm (ported from gnomad-carrier-frequency)

### 1. Fetch (one GraphQL call)
`gene.variants(dataset)` with: `variant_id, pos, ref, alt, flags`,
`transcript_consequence { is_canonical, lof, consequence_terms, major_consequence }`,
`exome/genome { ac, an, homozygote_count, filters, populations { id, ac, an, homozygote_count } }`,
plus `gene.clinvar_variants { variant_id, clinical_significance, review_status, gold_stars }`.
Join variants↔clinvar by `variant_id` string equality.

### 2. Qualifying-variant filter (defaults in parens)
- AC>0 guard (joint/exome+genome).
- `isHighConfidenceLoF` = canonical && lof=="HC".
- `isMissense` = canonical && consequence_terms ∩ {missense_variant, inframe_insertion, inframe_deletion}.
- `isPathogenicClinVar(threshold)` = significance has "pathogenic"/"likely pathogenic", NOT "conflicting", AND gold_stars >= threshold (default 2).
- Conflicting (opt-in, default OFF): significance has "conflicting" AND >= `conflicting_threshold`% (default 80) of that variant's ClinVar submissions are P/LP. Submissions fetched per conflicting candidate via `clinvar_variant(...).submissions`.
- Decision (short-circuit): if include_lof_hc && isLoFHC → qualify. elif isMissense → (include_missense && hasClinVarEvidence). elif hasClinVarEvidence → qualify. else drop. (hasClinVarEvidence = standard P/LP OR conflicting-resolved.)

### 3. Quality flags (default flag-only; exclusion opt-in, all default OFF)
- High AF (ACMG BA1): AF >= 0.05.
- High Hom: HWE-relative (observed_hom > 5x HWE-expected) or absolute (>=10).
- gnomAD-filtered: any non-PASS `filters`.
- Genomes-only: no exome data.
Flags annotate variants; `exclude_*` flags (default false) additionally drop them.

### 4. Per-population + global aggregation
For each population code (per version) and globally: per qualifying variant resolve
(ac, an, hom) joint-first (v4) else exome+genome sum. Then:
- `sumAF = Σ ac_i/an_i`; `totalAC = Σ ac_i`; `maxAN = max(an_i)` (display denominator).
- VCRᵢ = (ac_i − 2·hom_i)/(an_i/2).
- **method** (default `hom_exclusion`): GCR = 1 − ∏(1 − VCRᵢ). `hwe`: 2·(1−q)·q with q=sumAF. `simplified`: 2·sumAF.
- genetic_prevalence = sumAF² (always). bayesian_prevalence = genetic_prevalence · penetrance (default 1.0).
Founder-effect flag: pop CF > 5x global CF. Low-sample flag: maxAN < 1000.

### 5. Populations
- v4 (gnomad_r4): afr, amr, asj, eas, fin, mid, nfe, sas.
- v3 (gnomad_r3): afr, ami, amr, asj, eas, fin, nfe, sas.
- v2 (gnomad_r2_1): afr, amr, asj, eas, fin, nfe, oth, sas.
No sex-split. (Subcontinental v2 deferred — out of scope v1.)

## Tool surface

`compute_gene_carrier_frequency(gene_symbol | gene_id [one required], dataset=gnomad_r4,
include_lof_hc=True, include_missense=True, include_clinvar=True, clinvar_star_threshold=2,
include_conflicting_clinvar=False, conflicting_threshold=80, method="hom_exclusion"|"hwe"|"simplified",
penetrance=1.0, exclude_high_af=False, exclude_high_hom=False, exclude_gnomad_filtered=False,
exclude_genomes_only=False, response_mode="compact"|"full")`

Output: `{gene:{symbol,gene_id}, dataset, settings:{...}, global:{carrier_frequency, carrier_one_in,
genetic_prevalence, bayesian_prevalence, sum_af, total_ac, max_an, method}, populations:[{population,
carrier_frequency, carrier_one_in, genetic_prevalence, sum_af, total_ac, max_an, flags}], contributing_variants:{count, top:[...], truncated?}, qualifying_sources:{lof_hc, clinvar_only, both}, assumptions_note, citations[]}`.

Failure: `not_found` (gene) / `validation_failed` (no gene arg / bad params) / `upstream_unavailable`.
`_meta.next_commands` → `get_gene_variants`, `compute_carrier_frequency`, `get_clinvar_variant_details`.

## Architecture (Phase C patterns, 600-LOC cap)
- New `gene_carrier_variants.graphql` (enriched gene+clinvar). New client methods `get_gene_carrier_variants`, plus conflicting-submissions fetch (reuse `clinvar_variant`).
- New `gnomad_link/services/gene_carrier_math.py` — pure functions (effective af, VCR, GCR, hwe, simplified, hwe-expected-hom, per-pop aggregate, prevalence). Golden-tested.
- New `gnomad_link/services/gene_carrier_filters.py` — qualifying-variant predicates + quality flags. Unit-tested.
- New `gnomad_link/services/gene_carrier_service.py` — orchestrate fetch→annotate→filter→aggregate. Thin `FrequencyService` delegate.
- New `gnomad_link/mcp/gene_carrier_shaping.py` — compact output.
- New `gnomad_link/mcp/tools/gene_carrier.py` — `register_gene_carrier_tools`. Wire __init__, resources.py (tools, token_cost_hints ≤80, tool_categories["gene"]), EXPECTED_TOOLS.

## Invariants
Every module <600 LOC; `relax_output_schema`; `READ_ONLY_OPEN_WORLD`; `run_mcp_tool` envelope; safety meta; capabilities parity gate; no new ruff/mypy ignores; offline unit tests + one `integration`-marked live CFTR test.
