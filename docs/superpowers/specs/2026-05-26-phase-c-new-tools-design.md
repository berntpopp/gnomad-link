# Phase C — Five New MCP Tools (Design Spec)

> Historical record

Status: approved design, pre-plan
Date: 2026-05-26
Pairs with plan: `docs/superpowers/plans/2026-05-26-phase-c-new-tools.md`

## Goal

Add the five tools deferred in the LLM-consumer review / facade-polish "Out of
Scope (deferred)" section, taking the hand-authored MCP facade from 16 to 21
tools. Each tool follows the existing registration pattern exactly and preserves
all current invariants (relaxed output schemas, error envelopes, research-use
safety meta, capabilities parity, 600-LOC cap).

The five tools:

- **C1 `get_coverage`** — gnomAD per-base / scalar coverage so an LLM can judge
  whether `AF = 0` is trustworthy at a locus.
- **C2 `compare_variant_across_datasets`** — side-by-side `gnomad_r2_1` / `r3` /
  `r4` frequencies for one variant. Pure composition.
- **C3 `compute_carrier_frequency`** — local Hardy-Weinberg carrier / affected
  frequency for `AR` / `AD` / `XL` inheritance. Zero upstream cost beyond the
  one frequency call. Reduces LLM math errors.
- **C4 `get_gene_summary`** — single-call fan-out: gene constraint + canonical /
  MANE transcript + top pathogenic ClinVar + (best-effort) expression. Replaces
  a 4-call workflow.
- **C5 `search_structural_variants`** — resolver for opaque SV ids
  (`DEL_19_…`) by gene or region.

## Architecture

The facade is hand-authored FastMCP: each tool is a nested `async def` inside a
`register_<area>_tools(mcp, *, service_factory)` function, decorated with
`@mcp.tool(name=, title=, annotations=READ_ONLY_OPEN_WORLD, output_schema=relax_output_schema(...), tags={...})`,
taking `Annotated[type, Field(...)]` params, returning `dict[str, Any]` via
`await run_mcp_tool(name, call, context=McpErrorContext(...))`. `run_mcp_tool`
injects `_BASE_META` (`unsafe_for_clinical_use`, `gnomad_release`) on success and
converts exceptions to structured envelopes. Wiring a new module = create the
file + one import + one call line in `gnomad_link/mcp/tools/__init__.py`;
`facade.py` is untouched.

### Data-source tiering (verified against the live GraphQL schema + queries)

| Tool | Source | New GraphQL |
| --- | --- | --- |
| C2 compare | Loop existing `FrequencyService.get_variant_frequencies` per dataset + existing liftover | None |
| C3 carrier | Local math over existing `get_variant_frequencies` output | None |
| C4 gene_summary | `Gene.clinvar_variants` + `mane_select_transcript` + `pext` (GRCh37) + existing constraint | New `gene_summary.graphql` |
| C1 coverage | `Gene.coverage` / `Region.coverage(dataset!)` / `VariantDetails.coverage` | New `coverage.graphql` |
| C5 SV search | `Gene/Region.structural_variants(dataset:StructuralVariantDatasetId!)` | New `sv_search.graphql` |

### Module map (600-LOC cap; `shaping.py` is at 574 with no headroom)

All new shaping/math goes in **new** modules — never grown into `shaping.py`.

- Tools (`gnomad_link/mcp/tools/`): `carrier.py`, `comparison.py`,
  `gene_summary.py`, `coverage.py`, `sv_search.py`.
- Shaping / math: `gnomad_link/mcp/coverage_shaping.py`, `sv_shaping.py`,
  `gene_summary_shaping.py`, `comparison_shaping.py`;
  `gnomad_link/services/carrier_math.py` (pure functions, golden-value tested).
- Services: `gnomad_link/services/coverage_service.py`,
  `gnomad_link/services/structural_variant_service.py`. `frequency_service.py`
  (484 LOC) stays focused; C2/C3 reuse its `get_variant_frequencies` + liftover.
- GraphQL (`gnomad_link/graphql/queries/common/`): `coverage.graphql`
  (gene/region/variant ops), `sv_search.graphql` (gene/region ops),
  `gene_summary.graphql` (gene + clinvar_variants + mane + pext, with a GRCh37
  expression path). Existing `gene.graphql` / `GetVariantFrequencies.graphql`
  stay stable so `get_gene_details` / `get_variant_frequencies` do not churn.

## Components

### C1 `get_coverage`

`get_coverage(gene_symbol|gene_id | region | variant_id  [exactly one], dataset=gnomad_r4, response_mode="compact")`

- Scopes: gene → `Gene.coverage(dataset)`; region → `Region.coverage(dataset!)`
  (dataset is required upstream); variant → `VariantDetails.coverage` (scalar,
  no bins). Transcript and mitochondrial coverage are out of scope for v1.
- `CoverageBin`: `pos, mean, median, over_1..over_100`. Compact keep-set per
  bin: `mean, median, over_20, over_30`; bins capped per source with the
  self-describing `truncated` block; region requests reuse
  `cap_region_span(max_bp=100_000)`.
- Success: `{scope, identity, dataset, exome:{bins[], summary:{mean_coverage, fraction_over_20}, truncated?}, genome:{...}}`;
  variant scope returns scalar `{mean, median, over_20, over_30}` per source.
- Failure: `not_found` (unknown gene/region) / `validation_failed` (≠1 scope
  arg, bad id/region span) / `build_mismatch` (region coords vs dataset build) /
  `upstream_unavailable`.
- `_meta.next_commands` → `get_variant_frequencies`, `get_region`,
  `get_gene_details`.

### C2 `compare_variant_across_datasets`

`compare_variant_across_datasets(variant_id, datasets=["gnomad_r4","gnomad_r3","gnomad_r2_1"], populations?, auto_liftover=True)`

- Calls `get_variant_frequencies` once per dataset, reusing
  `shape_variant_frequencies` per dataset with identical compact knobs. When
  `auto_liftover` is set, a GRCh38 `variant_id` is lifted to GRCh37 via the
  existing liftover service for the `gnomad_r2_1` call (prevents the LLM footgun
  of sending a 38 id to r2_1).
- Datasets that 404 are reported as `{present:false}` (partial success), not a
  whole-call failure.
- Success: `{variant_id, datasets:{...}, comparison:{overall_af_by_dataset, per_population_af_deltas:[{population, <af per dataset>, delta}]}, build_notes}`.
- Excludes the r4-only `joint.freq_comparison_stats` in v1.
- Failure (whole call): `validation_failed` (bad id) / `build_mismatch` (cannot
  lift) / `upstream_unavailable` (all datasets fail).
- `_meta.next_commands` → `get_clinvar_variant_details`,
  `compute_carrier_frequency`.

### C3 `compute_carrier_frequency`

`compute_carrier_frequency(variant_id, inheritance:"AR"|"AD"|"XL", dataset=gnomad_r4, populations?, method:"hwe"|"hom_corrected"="hwe")`

Per-variant only (matches the signature); gene-level summation across variants
is out of scope. AF is `allele_frequency = ac/an` from the parsed
`PopulationFrequency` model. Sex-split is read from `_XX` / `_XY` population ids
already present in the `populations[]` list.

Formulas:

- **AR**: carrier frequency `2pq` (q = AF); affected/genetic-prevalence `q²`.
  `method="hom_corrected"` uses VCR `(ac − 2·homozygote_count) / (an/2)`
  (Guo 2019 / Zhu 2022) — the parsed model carries per-pop `homozygote_count`.
- **AD**: affected (≥1 pathogenic allele) frequency `1 − (1 − q)²` (≈ 2q),
  documented as literature-derived (Whiffin 2017 framing), not from the gCFCalc
  manuscript.
- **XL**: female carriers `2·q_XX` (q_XX from XX-restricted allele number);
  affected females `q_XX²`; affected males `q_XY` (hemizygous AF, no 2×, no
  square). Cite Hotakainen 2025 / Kandolin 2024.

Uncertainty (value-add the sibling/manuscript explicitly lack): a closed-form
**Wilson 95% CI** on AF propagated to the carrier frequency, attributed
conceptually to Schrodi 2015 (whose rigorous form is a Beta posterior; Wilson is
used to avoid a SciPy dependency).

- Per-population + overall + `summary.max_carrier_frequency_population`.
- `assumptions_note` (HWE, random mating, complete penetrance, single-variant,
  minimum-estimate framing) + `citations[]` (Schrodi 2015 doi:10.1007/s00439-015-1551-8;
  Karczewski 2020; plus Guo/Zhu for VCR and Hotakainen/Kandolin for XL).
- Edge cases: `AN = 0` → carrier frequency `null` (never `0`); `AC = 0` → flagged.
- Failure: `validation_failed` / `not_found` / `build_mismatch` /
  `upstream_unavailable`.
- `_meta.next_commands` → `get_clinvar_variant_details`,
  `get_variant_frequencies`.

### C4 `get_gene_summary`

`get_gene_summary(gene_symbol|gene_id, dataset=gnomad_r4, clinvar_limit=10, include_expression=True, response_mode="compact")`

- Constraint + `canonical_transcript_id` + `mane_select_transcript` come from a
  new `gene_summary` query on the summary dataset.
- `clinvar_summary` reads `Gene.clinvar_variants` (takes **no args** — no 100kb
  region cap), filters P/LP, ranks by `gold_stars` desc, caps at `clinvar_limit`
  (default 10) with a `truncated` block; reports `pathogenic_count` and a
  conflicting flag.
- `expression` is best-effort: `mean_pext` + top-5 GTEx tissues for the canonical
  transcript, fetched from **GRCh37 / `gnomad_r2_1`** (pext + GTEx are not
  populated on GRCh38). If empty, emit an `expression.unavailable` note rather
  than failing.
- Failure: `not_found` / `validation_failed`. ClinVar / expression enrichment is
  best-effort (partial-success flag, never a whole-call failure).
- `_meta.next_commands` → `get_gene_variants`, `get_clinvar_variant_details`,
  `get_coverage`.
- Requires one `integration`-marked test confirming GRCh37-vs-GRCh38 expression
  population for a known gene.

### C5 `search_structural_variants`

`search_structural_variants(gene_symbol|gene_id | region  [exactly one], sv_dataset="gnomad_sv_r4", sv_type?, min_length?, max_length?, limit=100, response_mode="compact")`

- gene → `Gene.structural_variants(sv_dataset!)`; region →
  `Region.structural_variants(sv_dataset!)`.
- Uses the **distinct** `StructuralVariantDatasetId` enum
  (`gnomad_sv_r4` default, `gnomad_sv_r2_1` = GRCh37) as its own `Literal` — NOT
  the standard dataset enum.
- No upstream filter args → `sv_type` / length filtering is client-side; the
  `shape_gene_variants` filter+cap+`to_restore` pattern applies. Reuses the
  existing `StructuralVariant` model (`variant_id, type, length, pos, end, af,
  ac, an, major_consequence`).
- SV ids are opaque (`DEL_19_…`) — docstring states this and the tool does NOT
  apply the SNV `variant_id` regex.
- Success: `{query:{gene|region, sv_dataset}, returned, total_seen, structural_variants:[...], truncated?}`.
  Empty result is success with `returned:0`.
- Failure: `validation_failed` (bad gene/region/sv_dataset) / `not_found` /
  `upstream_unavailable`.
- `_meta.next_commands` → `get_structural_variant`.

## Data flow

LLM → MCP tool → (`service_factory()` →) service method → GraphQL client →
gnomAD → parsed Pydantic model → tool-local shaping (`*_shaping.py` /
`carrier_math.py`) → `_meta` enrichment in the `call()` closure → `run_mcp_tool`
merges `_BASE_META` → relaxed-schema response. C2/C3/C4 fan out or compose
multiple service calls inside `call()`.

## Error handling

All tools route through `run_mcp_tool` so structured error envelopes
(`{success:false, error_code, message, _meta}`) survive SDK output validation
(every `output_schema` wrapped in `relax_output_schema`). Partial-success tools
(C2 per-dataset, C4 enrichment) surface presence/availability flags instead of
failing the whole call.

## Testing

- TDD: each task starts with a failing unit test. Unit tests are offline —
  services / GraphQL client mocked, returning Pydantic models or fixtures.
- `carrier_math.py` is tested against golden values (CFTR q=0.023 → 2pq=0.044942,
  q²=0.000529; GJB2 q=0.011 → 2pq=0.021758).
- Capabilities parity (`test_capabilities_tools_match_facade_tools`) is a hard CI
  gate: every new tool is added to `resources.py` (`tools`, `token_cost_hints`
  ≤80 chars, `tool_categories`) and to `EXPECTED_TOOLS` in
  `test_mcp_facade_surface.py` in the same commit.
- The single live expression-availability check for C4 is `integration`-marked
  (kept out of the default local CI path).

## Invariants

- Hand-authored facade pattern, one tool per `@mcp.tool`.
- Every `output_schema` wrapped in `relax_output_schema(...)`.
- `READ_ONLY_OPEN_WORLD` annotations, `tags`, examples, token-cost hint in the
  docstring, `_meta.next_commands` where a chain makes sense.
- Every tool uses `run_mcp_tool()` so error envelopes flow unchanged.
- Research-use safety meta preserved (`unsafe_for_clinical_use`,
  `gnomad_release`).
- 600-LOC cap per module; new shaping/services never grown into `shaping.py` or
  `frequency_service.py`. No `.loc-allowlist` raises.
- No widening of Ruff / mypy ignore lists.
- Unit tests offline under `tests/unit/`; live tests `integration`-marked.
- `resources.py` capabilities + `token_cost_hints` updated per tool.

## Open decisions (resolved)

- C1 scope: gene + region + per-variant (transcript / MT deferred).
- C2: compare all three datasets, auto-liftover for r2_1, exclude joint stats.
- C3: support all three inheritance modes; include Wilson CI + `hom_corrected`
  option; per-variant only.
- C4: extend the gene query (no region cap); include expression from GRCh37
  best-effort; top-10 P/LP ClinVar by gold stars.
- C5: gene + region entry, default `gnomad_sv_r4`, client-side filters.

## Out of scope

- Transcript-level and mitochondrial coverage (C1).
- r4-only `joint.freq_comparison_stats` in C2.
- Gene-level (multi-variant summed) carrier frequency in C3.
- Cross-MCP expression calls (e.g. gtex-link) in C4 — only gnomAD's own
  pext/GTEx is surfaced.
- Any new REST surface (facade remains MCP-only; REST stays `/health`).
- Clinical decision support — research use only.
