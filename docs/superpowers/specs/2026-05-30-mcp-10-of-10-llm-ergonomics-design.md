# MCP 10/10 LLM-Ergonomics Hardening — Design

Status: draft
Date: 2026-05-30
Owner: gnomAD Link MCP

## Motivation

An LLM consumer scored the server ~8.8/10 after exercising
`compute_gene_carrier_frequency` and `get_gene_details`. The two lowest, and
the only actionable, scores were:

- **Token efficiency (8/10):** the carrier tools re-emit a byte-identical
  `citations` list + multi-sentence `assumptions_note` on every call.
- **Payload weight on the heavy tool:** "even compact, carrier-frequency
  returns a lot — a one-line headline summary at the top would let me answer
  fast without parsing the full tree."

The "round-trip friction" point (deferred tools needing a ToolSearch hop) is a
host/harness behavior, not the server's, and is out of scope.

## Research grounding (Anthropic + MCP spec)

- *Writing tools for agents* — "return only high signal information… eschew
  low-level technical identifiers"; agents handle "natural language names…
  significantly more successfully than cryptic identifiers." → a plain-English
  **`headline`** string at the top of high-value payloads.
- *Writing tools for agents* — `response_format` concise/detailed uses ~1/3 the
  tokens; we already ship `response_mode=compact|full`, which maps cleanly.
- *Effective context engineering* + *MCP resources spec* — verbose, identical
  static prose belongs in a **resource with a stable URI** fetched once, with
  results carrying a short pointer ("lightweight identifiers… resolved at
  runtime").
- **Guardrail (must not regress):** groundability cannot depend on a second
  fetch. Keep the one-line research-use safety flag inline on every result
  (already in `_meta`), and keep **short-form** author-year citations + a short
  assumptions clause inline in compact mode. Demote only the long bibliographic
  prose to the resource.

## Changes

### 1. Headline field (additive, all output schemas already allow extra keys via `relax_output_schema`)

Add a top-level `headline: str` (plain English, < ~200 chars, no clinical
phrasing) to the four high-value tools. Distinct key from the existing
structured `summary` object (no collision).

| Tool | Headline (confirmed field paths) |
|---|---|
| `compute_gene_carrier_frequency` | `{gene.symbol} ({dataset}): carrier frequency 1 in {global.carrier_one_in} globally; highest 1 in {populations[0].carrier_one_in} ({populations[0].population}); {contributing_variants.count} qualifying variants. Research use only.` |
| `compute_carrier_frequency` | `{variant_id} ({inheritance}/{dataset}): carrier frequency ~{overall.carrier_frequency} …` (inheritance-aware: AR carrier_frequency, AD affected_or_carrier_frequency, XL female_carrier_frequency) |
| `get_variant_frequencies` | `{variant_id} {major_consequence}: AF {summary.overall_af} ({dataset}); highest in {summary.max_pop} ({summary.max_pop_af}).` |
| `get_gene_details` | `{symbol} ({gene_id}): pLI {gnomad_constraint.pli}, LoF o/e {gnomad_constraint.oe_lof}; {chrom}:{start}-{stop} ({reference_genome}).` |

All builders are null-safe: any missing field degrades gracefully (skip the
clause or say "unknown") and never raises.

Builders live in a new pure module `gnomad_link/mcp/headline.py` (testable,
keeps tool/shaping files lean and under the 600-LOC cap).

### 2. Provenance de-duplication

New module `gnomad_link/mcp/provenance.py` — single source of truth for the
carrier citation/assumptions text (currently duplicated across `carrier.py` and
`gene_carrier_shaping.py`). Holds, keyed by topic `variant_carrier` /
`gene_carrier`:

- `*_FULL` — full bibliographic citations + full assumptions prose.
- `*_SHORT` — author-year citation tokens + a one-sentence assumptions clause
  (the short assumptions MUST still contain "Hardy-Weinberg"; the short variant
  citations MUST still contain a "Schrodi" token and the gene citations a
  "Karczewski" token, to preserve groundability and the existing contracts).
- `provenance_block(topic, *, full) -> {assumptions_note, citations, citations_ref}`
  where `citations_ref = "gnomad://citations"`.

Behavior, gated on the existing `response_mode` lever:

- **compact (default):** short citations + short assumptions_note +
  `citations_ref`. (~400 bytes lighter per call than today.)
- **full:** full citations + full assumptions_note + `citations_ref`.

`compute_carrier_frequency` gains a `response_mode: compact|full = compact`
param for symmetry with `compute_gene_carrier_frequency` (which already has it).

New MCP resource `gnomad://citations` (registered next to
`gnomad://capabilities`) returns the full registry keyed by topic plus
`gnomad_release` and the research-use notice, so an LLM resolves it once.

### 3. Discoverability

Update `get_capabilities_resource()`:
- `output_cheatsheet`: add `"headline_field": "headline"`.
- advertise the `gnomad://citations` resource.
- note headline availability in the relevant `token_cost_hints` / docstrings.

## Non-goals / invariants

- Do not move `unsafe_for_clinical_use` or `gnomad_release` out of `_meta` (5
  test files pin them there).
- Do not rename or retype the existing `summary` objects on
  `compute_carrier_frequency`, `get_variant_frequencies`,
  `get_clinvar_variant_details` (tests pin them as dicts).
- Preserve `_meta.next_commands` on every tool.
- Keep every module < 600 LOC.

## Test plan

- New `tests/unit/mcp/test_headline.py` — each builder: accurate render +
  null-safety (missing constraint, empty populations, variant-not-found).
- New `tests/unit/mcp/test_provenance.py` — short vs full block, `citations_ref`
  present, short forms retain Schrodi/Karczewski/Hardy-Weinberg tokens.
- Extend carrier + gene_carrier_shaping tests: compact emits short +
  citations_ref; full emits full prose; headline present.
- New resource test: `gnomad://citations` returns both topics + release.
- `make ci-local` green; live MCP smoke for headline accuracy + token delta;
  adversarial review that the guardrail did not regress.
