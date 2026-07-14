# gnomad-link

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![CI](https://github.com/berntpopp/gnomad-link/actions/workflows/ci.yml/badge.svg)](https://github.com/berntpopp/gnomad-link/actions/workflows/ci.yml)
[![Conformance](https://github.com/berntpopp/gnomad-link/actions/workflows/conformance.yml/badge.svg)](https://github.com/berntpopp/gnomad-link/actions/workflows/conformance.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

An MCP server over [gnomAD](https://gnomad.broadinstitute.org/), the Genome
Aggregation Database: variant allele frequencies, gene constraint, ClinVar
significance, coverage, structural and mitochondrial variants, and liftover.
Streamable HTTP only; FastAPI is a thin host serving `/health`, and every domain
capability is an MCP tool.

> [!IMPORTANT]
> Research use only. Not clinical decision support. Do not use for diagnosis,
> treatment, triage, or patient management.

## Why

gnomAD's only programmatic surface is a public GraphQL API, and three things make
it hostile to an LLM. Its schema is **version-specific** — `gnomad_r2_1` (GRCh37),
`gnomad_r3` and `gnomad_r4` (GRCh38) need different query documents, so the caller
must know which release answers which question. It is **id-first**: every variant
lookup wants a fully-resolved `CHROM-POS-REF-ALT`, so an rsID, an HGVS string or a
half-remembered coordinate is a dead end. And it is **unbounded**: a large gene
returns tens of thousands of variant rows (CFTR's payload is roughly 13 MB), which
buries a model's context long before it reaches an answer.

This server routes the right schema per dataset, resolves loose input to canonical
ids, and returns compact, capped responses that declare what they truncated. It
also computes what gnomAD does not: Hardy-Weinberg carrier frequencies, per
variant and per gene.

## Quick start

The server is hosted — no install, no data build:

```bash
claude mcp add --transport http gnomad-link https://gnomad-link.genefoundry.org/mcp
```

To run it locally (Python 3.12+, [uv](https://github.com/astral-sh/uv)):

```bash
uv sync --group dev
make dev                    # unified FastAPI /health host + MCP at /mcp on :8000
claude mcp add --transport http gnomad-link http://127.0.0.1:8000/mcp
```

There is no ingest step: queries hit the gnomAD API live, and it needs no API key.
The Docker stack (`make docker-up`) publishes on `GNOMAD_LINK_HOST_PORT`, default
`8020`, so its endpoint is `http://127.0.0.1:8020/mcp`.

Smoke-test the endpoint — note the dual `Accept` header, which Streamable HTTP
requires and which is the usual reason a hand-rolled `curl` fails:

```bash
curl -sS http://127.0.0.1:8000/mcp \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## Tools

| Tool | Purpose |
|------|---------|
| `get_variant_frequencies` | Allele counts and frequencies per population for a variant |
| `get_variant_details` | Full variant annotation: consequences, predictors, ClinVar |
| `compare_variant_across_datasets` | Compare one variant's allele frequencies across gnomAD releases |
| `resolve_variant_id` | Resolve an rsID, partial coordinate, or loose text to a canonical variant id |
| `search_variants` | Deprecated alias for `resolve_variant_id` |
| `get_gene_details` | Gene constraint metrics (pLI, o/e LoF) and canonical transcript |
| `get_gene_variants` | Per-variant rows within a gene, filtered and capped |
| `get_gene_summary` | One-shot gene dossier: constraint, transcripts, top ClinVar, expression |
| `search_genes` | Find genes by symbol, alias, or Ensembl id |
| `get_clinvar_variant_details` | ClinVar significance, review status, gold stars, submissions |
| `get_clinvar_meta` | ClinVar release metadata (deprecated; use `get_server_capabilities`) |
| `compute_variant_liftover` | Convert a variant id between GRCh37 and GRCh38 |
| `get_region` | Genes and ClinVar variants in a genomic region |
| `get_coverage` | Read-depth coverage over a gene, region, or variant |
| `get_transcript_details` | Exon structure plus a compact GTEx tissue-expression summary |
| `get_structural_variant` | Structural variant record by id |
| `search_structural_variants` | Structural variants overlapping a gene or region |
| `get_mitochondrial_variant` | Mitochondrial variant record, with heteroplasmy |
| `compute_carrier_frequency` | Carrier frequency from a single variant (AR / AD / X-linked) |
| `compute_gene_carrier_frequency` | Gene-level recessive carrier rate across qualifying variants |
| `get_server_capabilities` | Tools, datasets, population codes, live ClinVar release, limits |
| `get_diagnostics` | Recent errors, schema drift, and upstream health |

Leaf names are intentionally unprefixed, per
[Tool-Naming Standard v1](https://github.com/berntpopp/genefoundry-router/blob/main/docs/TOOL-NAMING-STANDARD-v1.md).
The canonical gateway namespace token is `gnomad`: behind
[genefoundry-router](https://github.com/berntpopp/genefoundry-router) these
surface as `gnomad_<tool>` (e.g. `gnomad_get_variant_frequencies`). The MCP server
identity (`serverInfo.name`) is `gnomad-link`.

## Data & provenance

Served live from the public gnomAD GraphQL API — no local database, no bundle, no
API key. The upstream release (gnomAD 4.1.0) is stamped in every response's
`_meta`, and the ClinVar release date is read live from gnomAD. `gnomad_r4`
(GRCh38) is the default dataset; `gnomad_r2_1` is GRCh37, so a variant id only
means something alongside its build.

gnomAD data is CC0, but attribution is requested and some annotations carry
stricter licences of their own. Cite Karczewski et al. 2020 (Nature 581:434-443)
and, for v4, Chen et al. 2024 (Nature 625:92-100). Full detail — datasets,
freshness, licensing quirks, and citations — is in
[docs/data.md](docs/data.md).

## Documentation

- [Data & provenance](docs/data.md) — datasets, freshness, licensing, citations.
- [Configuration](docs/configuration.md) — every environment variable, the cache and
  concurrency knobs, and the Host/Origin request boundary.
- [Architecture](docs/architecture.md) — the MCP facade, service layer, and GraphQL routing.
- [Usage](docs/usage.md) — worked `curl` calls against each tool.
- [MCP connection guide](docs/MCP_CONNECTION_GUIDE.md) — Claude Code, Claude Desktop,
  ChatGPT, and Gemini clients.
- [Deployment](docker/README.md) — Docker Compose overlays, hardening, and the
  Nginx Proxy Manager path.
- [Development](docs/development.md) — setup, test layout, and the release process.
- [gnomAD GraphQL reference](docs/gnomad_graphql/) — generated upstream schema docs.

## Contributing

See [AGENTS.md](AGENTS.md) for engineering conventions and the repository layout.
`make ci-local` is the definition-of-done gate: format, lint, line budget, README
standard, mypy, and tests. It must be green before handoff.

## License

Code: [MIT](LICENSE). Data: gnomAD is released under the Creative Commons Zero
(CC0) Public Domain Dedication — attribution is requested rather than required,
re-identification of participants is forbidden, and individual annotations
(SpliceAI, for one) may carry their own stricter terms. See the
[gnomAD terms of use](https://gnomad.broadinstitute.org/policies).
