# MCP 10/10 LLM-Ergonomics — Plan

> Historical record

Spec: ../specs/2026-05-30-mcp-10-of-10-llm-ergonomics-design.md

## Tasks

- [ ] T1. `provenance.py`: central citation/assumptions registry + `provenance_block(topic, *, full)`; `gnomad://citations` payload builder.
- [ ] T2. `headline.py`: 4 null-safe headline builders (gene_carrier, variant_carrier, variant_frequencies, gene_details).
- [ ] T3. Wire carrier tools: `compute_carrier_frequency` (+ response_mode, provenance_block, headline) and `compute_gene_carrier_frequency`/`shape_gene_carrier` (provenance_block, headline).
- [ ] T4. Wire `get_variant_frequencies` + `get_gene_details` headlines.
- [ ] T5. Register `gnomad://citations` resource; update capabilities (output_cheatsheet, resources, hints).
- [ ] T6. Tests: test_headline, test_provenance, extend carrier/gene_carrier/shaping/resource tests.
- [ ] T7. `make ci-local`; live MCP smoke (headline + token delta); adversarial review; Docker rebuild.
