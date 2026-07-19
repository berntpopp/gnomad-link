# Full-Tool Audit Response (F1-F6) — Plan

> Historical record

Source: an LLM consumer's 22-tool live audit (8.3/10) with six findings.
Status: implemented (commit bb86db9); ci-local green (429 unit tests).

## Findings and resolutions

- [x] **F1 (liftover one-directional)** — gnomAD's liftover table is keyed on the
  GRCh37 `source`, so GRCh38->GRCh37 must query `liftover_variant_id`, not
  `source_variant_id`. Query the correct argument per direction; expose
  `target_variant_id`, `target_reference_genome`, `query_type`. Verified live
  both ways (`1-55051215-G-GA` <-> `1-55516888-G-GA`).
- [x] **F2 (clinvar_release_date null)** — `get_server_capabilities` enriches the
  live ClinVar date best-effort (process-cached) instead of hard-null.
- [x] **F3 (SV not_found dead-end)** — SV tools route not_found to
  `search_structural_variants`/`search_genes`, not the SNV-only
  `resolve_variant_id`; real SV example (`BND_chr12_e99836ac`) + discovery-first
  docstring.
- [x] **F4 (gene-search omits family members)** — root cause is UPSTREAM gnomAD
  autocomplete (it never returns GRIN1/GRIN2B for `GRIN`; re-ranking cannot
  surface unreturned genes). Added an actionable `search_hint` + capabilities
  limitation steering to full-symbol queries. (Re-ranking tiebreaker rejected:
  it cannot fix the omission and would reorder same-tier prefix matches against
  the existing contract.)
- [x] **F5 (carrier sex-split leakage)** — AR/AD suppress XX/XY/_XX/_XY pseudo-
  populations (kept for XL); fixes the max-population pick and the headline;
  adds per-population Wilson CIs.
- [x] **F6 (opaque concurrency timeouts)** — a saturated concurrency queue
  returns a fast retryable `rate_limited` envelope (bounded
  `GNOMAD_QUEUE_WAIT_TIMEOUT`); capabilities advertises `max_concurrent_requests`.

## Verification

- Unit: +11 tests across liftover, carrier, error-taxonomy, capabilities,
  base-client, search-ranking.
- Live: liftover both directions, ClinVar date, real SV id, gnomAD `GRIN`
  upstream omission all confirmed against the live API.
- Pending: Docker rebuild + live MCP smoke; adversarial diff review.
