# Data and provenance

## Upstream

All data is served live from the public [gnomAD GraphQL
API](https://gnomad.broadinstitute.org/api) (`GNOMAD_API_URL`). The API is
unauthenticated — there is no API key, and no data-build step: this server ships
**no local database and no data bundle**. It is a shaping, resolving and caching
proxy in front of a live upstream.

The current upstream release is stamped in every MCP response's `_meta`
(`GNOMAD_DATA_RELEASE`, gnomAD **4.1.0**), so a caller can always cite the exact
data version behind a claim. The ClinVar release date served by gnomAD is fetched
live and surfaced by `get_server_capabilities` (and by the deprecated
`get_clinvar_meta`).

## Datasets

The server routes each query to a version-specific GraphQL document
(`gnomad_link/graphql/queries/{v2,v3,v4,common}/`) because the gnomAD schema
differs per release.

| Dataset | Reference build | Content |
|---------|-----------------|---------|
| `gnomad_r2_1` | GRCh37 | Exomes, 125k+ individuals |
| `gnomad_r3` | GRCh38 | Genomes, 76k+ individuals |
| `gnomad_r4` | GRCh38 | Latest release, 730k+ individuals — **the default** |

Because `gnomad_r2_1` is GRCh37 and the others are GRCh38, a variant id is only
meaningful together with its build. `compute_variant_liftover` converts ids in
both directions, and `compare_variant_across_datasets` compares one variant's
allele frequencies across releases.

## What the data covers

Allele counts and frequencies broken down by gnomAD's genetic-ancestry groups,
gene constraint metrics (pLI, o/e LoF), read-depth coverage, ClinVar clinical
significance, structural variants, mitochondrial variants (with heteroplasmy),
and transcript-level annotation (with optional GTEx expression).

Carrier-frequency tools (`compute_carrier_frequency`,
`compute_gene_carrier_frequency`) derive estimates under Hardy-Weinberg
assumptions. They are **minimum estimates** bounded by gnomAD ascertainment and
ClinVar completeness, and every response carries its own citations, an
assumptions note, and a `citations_ref` pointer to the `gnomad://citations`
resource.

## Freshness

There is no ingest and no refresh job. Queries hit gnomAD live, fronted by an
in-memory cache (`CACHE_SIZE`, default 1024 entries; `CACHE_TTL_MINUTES`, default
60). Bump `GNOMAD_DATA_RELEASE` in `gnomad_link/mcp/resources.py` when upstream
cuts a new release.

Upstream politeness is enforced by a bounded concurrency limiter
(`GNOMAD_MAX_CONCURRENCY`, default 5) with a jittered retry layer for residual
429s; see [configuration.md](configuration.md).

## Licence

gnomAD data is released under the **Creative Commons Zero (CC0) Public Domain
Dedication**: there are no restrictions or embargoes on publishing results
derived from it, and no attribution is legally required. The gnomAD consortium
nevertheless **requests acknowledgement and a link back**, and users agree **not
to attempt to re-identify participants**. See the [gnomAD terms of
use](https://gnomad.broadinstitute.org/policies).

> **Licensing quirk worth knowing:** individual *annotations* served alongside
> gnomAD data may carry their own, more restrictive licences — SpliceAI, for
> example, is CC BY-NC 4.0 (academic and non-commercial use). CC0 covers the
> gnomAD data itself, not every third-party annotation surfaced with it. Callers
> are responsible for the terms of any annotation they use.

This repository's own code is MIT (see [LICENSE](../LICENSE)).

## Citation

If you use this server in research, cite gnomAD:

```text
Karczewski, K.J., Francioli, L.C., Tiao, G. et al.
The mutational constraint spectrum quantified from variation in 141,456 humans.
Nature 581, 434-443 (2020).
```

For gnomAD v4 (the default dataset):

```text
Chen, S., Francioli, L.C., Goodrich, J.K. et al.
A genomic mutational constraint map using variation in 76,156 human genomes.
Nature 625, 92-100 (2024).
```

Carrier-frequency results additionally cite the methodological sources inlined in
the response (Schrodi et al. 2015; Karczewski et al. 2022; and others — read
`gnomad://citations` for the full list).

## Acknowledgements

- [gnomAD](https://gnomad.broadinstitute.org/) — the Genome Aggregation Database.
- [Broad Institute](https://www.broadinstitute.org/) — gnomAD maintainers.

Further gnomAD reading: the [gnomAD browser](https://gnomad.broadinstitute.org/),
the [GraphQL API](https://gnomad.broadinstitute.org/api), the [GA4GH standards
integration](https://gnomad.broadinstitute.org/news/2023-11-ga4gh-gks/), and the
generated [GraphQL reference](gnomad_graphql/) in this repository.
