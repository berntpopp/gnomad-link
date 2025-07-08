# gnomAD GraphQL API Reference

*Generated on 2025-07-08 12:25:22*

## 📚 Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Available Queries](#available-queries)
  - [Variant Queries](#variant-queries)
  - [Gene Queries](#gene-queries)
  - [Search Queries](#search-queries)
  - [Clinical Data Queries](#clinical-data-queries)
  - [Utility Queries](#utility-queries)
- [Data Types](#data-types)
- [Enumerations](#enumerations)
- [Best Practices](#best-practices)

---

## Overview

The gnomAD (Genome Aggregation Database) GraphQL API provides programmatic access to:

- **🧬 Genetic Variants**: Population frequencies, functional annotations, quality metrics
- **🧪 Clinical Data**: ClinVar annotations, disease associations, pathogenicity
- **📊 Gene Information**: Constraint scores, expression data, transcript details
- **🔍 Search Functions**: Find variants and genes by various criteria
- **🛠️ Utilities**: Coordinate liftover, metadata, co-occurrence analysis

### Available Datasets

| Dataset | Reference | Samples | Description |
|---------|-----------|---------|-------------|
| `gnomad_r4` | GRCh38 | 807,162 | Latest release (v4.1) |
| `gnomad_r3` | GRCh38 | 76,156 | Previous release (v3.1.2) |
| `gnomad_r2_1` | GRCh37 | 141,456 | Legacy release (v2.1.1) |
| `gnomad_sv_r4` | GRCh38 | - | Structural variants |
| `gnomad_cnv_r4` | GRCh38 | - | Copy number variants |

---

## Quick Start

### API Endpoint
```
POST https://gnomad.broadinstitute.org/api/
Content-Type: application/json
```

### Basic Query Structure
```graphql
query {
  variant(variantId: "1-55516888-G-A", dataset: gnomad_r4) {
    variant_id
    genome {
      af
    }
  }
}
```

---

## Available Queries

### Variant Queries

#### `copy_number_variant`

No description available

**Returns:** `CopyNumberVariantDetails`

<details>
<summary><strong>Arguments</strong></summary>

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `variantId` | `String!` | Yes | - |
| `dataset` | `CopyNumberVariantDatasetId!` | Yes | - |

</details>

<details>
<summary><strong>Example</strong></summary>

```graphql
query {
  copy_number_variant(variantId: "1-55516888-G-A", dataset: gnomad_r4) {
    variant_id
    genome { af }
  }
}
```

</details>

#### `mitochondrial_variant`

No description available

**Returns:** `MitochondrialVariantDetails`

<details>
<summary><strong>Arguments</strong></summary>

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `variant_id` | `String` | No | - |
| `dataset` | `DatasetId!` | Yes | - |

</details>

<details>
<summary><strong>Example</strong></summary>

```graphql
query {
  mitochondrial_variant(variant_id: "1-55516888-G-A", dataset: gnomad_r4) {
    variant_id
    genome { af }
  }
}
```

</details>

#### `multiNucleotideVariant`

No description available

**Returns:** `MultiNucleotideVariantDetails`

<details>
<summary><strong>Arguments</strong></summary>

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `variant_id` | `String!` | Yes | - |
| `dataset` | `DatasetId!` | Yes | - |

</details>

<details>
<summary><strong>Example</strong></summary>

```graphql
query {
  multiNucleotideVariant(variant_id: "1-55516888-G-A", dataset: gnomad_r4) {
    # Add fields here
  }
}
```

</details>

#### `structural_variant`

No description available

**Returns:** `StructuralVariantDetails`

<details>
<summary><strong>Arguments</strong></summary>

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `variantId` | `String!` | Yes | - |
| `dataset` | `StructuralVariantDatasetId!` | Yes | - |

</details>

<details>
<summary><strong>Example</strong></summary>

```graphql
query {
  structural_variant(variantId: "1-55516888-G-A", dataset: gnomad_r4) {
    variant_id
    genome { af }
  }
}
```

</details>

#### `variant`

No description available

**Returns:** `VariantDetails`

<details>
<summary><strong>Arguments</strong></summary>

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `variantId` | `String` | No | - |
| `rsid` | `String` | No | - |
| `vrsId` | `String` | No | - |
| `dataset` | `DatasetId!` | Yes | - |

</details>

<details>
<summary><strong>Example</strong></summary>

```graphql
query {
  variant(variantId: "1-55516888-G-A", dataset: gnomad_r4) {
    variant_id
    genome { af }
  }
}
```

</details>

#### `variant_cooccurrence`

No description available

**Returns:** `VariantCooccurrence`

<details>
<summary><strong>Arguments</strong></summary>

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `variants` | `[String!]!` | Yes | - |
| `dataset` | `DatasetId!` | Yes | - |

</details>

<details>
<summary><strong>Example</strong></summary>

```graphql
query {
  variant_cooccurrence(variants: "1-55516888-G-A", dataset: gnomad_r4) {
    variant_id
    genome { af }
  }
}
```

</details>

### Gene Queries

#### `gene`

No description available

**Returns:** `Gene`

<details>
<summary><strong>Arguments</strong></summary>

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `gene_id` | `String` | No | - |
| `gene_symbol` | `String` | No | - |
| `reference_genome` | `ReferenceGenomeId!` | Yes | - |

</details>

<details>
<summary><strong>Example</strong></summary>

```graphql
query {
  gene(gene_id: "ENSG00000139618", gene_symbol: "BRCA2", reference_genome: GRCh38) {
    gene_id
    symbol
  }
}
```

</details>

#### `transcript`

No description available

**Returns:** `Transcript`

<details>
<summary><strong>Arguments</strong></summary>

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `transcript_id` | `String!` | Yes | - |
| `reference_genome` | `ReferenceGenomeId!` | Yes | - |

</details>

<details>
<summary><strong>Example</strong></summary>

```graphql
query {
  transcript(transcript_id: "example", reference_genome: GRCh38) {
    # Add fields here
  }
}
```

</details>

### Search Queries

#### `gene_search`

No description available

**Returns:** `[GeneSearchResult!]!`

<details>
<summary><strong>Arguments</strong></summary>

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `query` | `String!` | Yes | - |
| `reference_genome` | `ReferenceGenomeId!` | Yes | - |

</details>

<details>
<summary><strong>Example</strong></summary>

```graphql
query {
  gene_search(query: "APOE", reference_genome: GRCh38) {
    gene_id
    symbol
  }
}
```

</details>

#### `variant_search`

No description available

**Returns:** `[VariantSearchResult!]!`

<details>
<summary><strong>Arguments</strong></summary>

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `query` | `String!` | Yes | - |
| `dataset` | `DatasetId!` | Yes | - |

</details>

<details>
<summary><strong>Example</strong></summary>

```graphql
query {
  variant_search(query: "APOE", dataset: gnomad_r4) {
    variant_id
    genome { af }
  }
}
```

</details>

### Clinical Data Queries

#### `clinvar_variant`

No description available

**Returns:** `ClinVarVariantDetails`

<details>
<summary><strong>Arguments</strong></summary>

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `variant_id` | `String!` | Yes | - |
| `reference_genome` | `ReferenceGenomeId!` | Yes | - |

</details>

<details>
<summary><strong>Example</strong></summary>

```graphql
query {
  clinvar_variant(variant_id: "1-55516888-G-A", reference_genome: GRCh38) {
    variant_id
    genome { af }
  }
}
```

</details>

### Utility Queries

#### `liftover`

No description available

**Returns:** `[LiftoverResult!]!`

<details>
<summary><strong>Arguments</strong></summary>

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `source_variant_id` | `String` | No | - |
| `liftover_variant_id` | `String` | No | - |
| `reference_genome` | `ReferenceGenomeId!` | Yes | - |

</details>

<details>
<summary><strong>Example</strong></summary>

```graphql
query {
  liftover(source_variant_id: "1-55516888-G-A", liftover_variant_id: "1-55516888-G-A", reference_genome: GRCh38) {
    # Add fields here
  }
}
```

</details>

#### `meta`

No description available

**Returns:** `BrowserMetadata!`

<details>
<summary><strong>Example</strong></summary>

```graphql
query {
  meta {
    # Add fields here
  }
}
```

</details>

#### `region`

No description available

**Returns:** `Region!`

<details>
<summary><strong>Arguments</strong></summary>

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `chrom` | `String!` | Yes | - |
| `start` | `Int!` | Yes | - |
| `stop` | `Int!` | Yes | - |
| `reference_genome` | `ReferenceGenomeId!` | Yes | - |

</details>

<details>
<summary><strong>Example</strong></summary>

```graphql
query {
  region(chrom: "example", start: 123, stop: 123, reference_genome: GRCh38) {
    # Add fields here
  }
}
```

</details>

#### `short_tandem_repeat`

No description available

**Returns:** `ShortTandemRepeatDetails`

<details>
<summary><strong>Arguments</strong></summary>

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `id` | `String!` | Yes | - |
| `dataset` | `DatasetId!` | Yes | - |

</details>

<details>
<summary><strong>Example</strong></summary>

```graphql
query {
  short_tandem_repeat(id: "example", dataset: gnomad_r4) {
    # Add fields here
  }
}
```

</details>

#### `short_tandem_repeats`

No description available

**Returns:** `[ShortTandemRepeat!]!`

<details>
<summary><strong>Arguments</strong></summary>

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `dataset` | `DatasetId!` | Yes | - |

</details>

<details>
<summary><strong>Example</strong></summary>

```graphql
query {
  short_tandem_repeats(dataset: gnomad_r4) {
    # Add fields here
  }
}
```

</details>

---

## Data Types

The API uses the following type categories:

### Core Variant Types

| Type | Description | Key Fields |
|------|-------------|------------|
| [Variant](#type-variant) |  | `variant_id`, `reference_genome`, `chrom` |
| [VariantDetails](#type-variantdetails) |  | `variant_id`, `reference_genome`, `chrom` |
| [VariantSequencingTypeData](#type-variantsequencingtypedata) |  | `ac`, `an`, `homozygote_count` |
| [VariantJointSequencingTypeData](#type-variantjointsequencingtypedata) |  | `ac`, `an`, `homozygote_count` |
| [VariantQualityMetrics](#type-variantqualitymetrics) |  | `allele_balance`, `genotype_depth`, `genotype_quality` |

### Specialized Variant Types

| Type | Description | Key Fields |
|------|-------------|------------|
| [MitochondrialVariant](#type-mitochondrialvariant) |  | `ac_het`, `ac_hom`, `an` |
| [MitochondrialVariantDetails](#type-mitochondrialvariantdetails) |  | `ac_het`, `ac_hom`, `ac_hom_mnv` |
| [StructuralVariant](#type-structuralvariant) |  | `ac`, `an`, `af` |
| [StructuralVariantDetails](#type-structuralvariantdetails) |  | `age_distribution`, `algorithms`, `alts` |
| [CopyNumberVariant](#type-copynumbervariant) |  | `sc`, `sn`, `sf` |
| [CopyNumberVariantDetails](#type-copynumbervariantdetails) |  | `alts`, `sc`, `sn` |
| [MultiNucleotideVariantDetails](#type-multinucleotidevariantdetails) |  | `variant_id`, `reference_genome`, `chrom` |

### Population & Frequency Data

| Type | Description | Key Fields |
|------|-------------|------------|
| [VariantPopulation](#type-variantpopulation) |  | `id`, `ac`, `an` |
| [VariantFilteringAlleleFrequency](#type-variantfilteringallelefrequency) |  | `popmax`, `popmax_population` |
| [VariantLocalAncestryPopulation](#type-variantlocalancestrypopulation) |  | `id`, `ac`, `an` |
| [MitochondrialVariantPopulation](#type-mitochondrialvariantpopulation) |  | `id`, `an`, `ac_het` |
| [StructuralVariantPopulation](#type-structuralvariantpopulation) |  | `id`, `ac`, `an` |
| [CopyNumberVariantPopulation](#type-copynumbervariantpopulation) |  | `id`, `sc`, `sn` |
| [Fafmax](#type-fafmax) |  | `faf95_max`, `faf95_max_gen_anc`, `faf99_max` |
| [VAGrpMaxFAF95](#type-vagrpmaxfaf95) |  | `frequency`, `confidenceInterval`, `groupId` |

### Gene & Transcript Types

| Type | Description | Key Fields |
|------|-------------|------------|
| [Gene](#type-gene) |  | `reference_genome`, `gene_id`, `gene_version` |
| [Transcript](#type-transcript) |  | `reference_genome`, `transcript_id`, `transcript_version` |
| [Exon](#type-exon) |  | `feature_type`, `start`, `stop` |
| [GeneTranscript](#type-genetranscript) |  | `reference_genome`, `transcript_id`, `transcript_version` |
| [TranscriptGene](#type-transcriptgene) |  | `reference_genome`, `gene_id`, `gene_version` |
| [RegionGene](#type-regiongene) |  | `gene_id`, `symbol`, `start` |
| [RegionGeneTranscript](#type-regiongenetranscript) |  | `transcript_id`, `start`, `stop` |
| [ManeSelectTranscript](#type-maneselecttranscript) |  | `ensembl_id`, `ensembl_version`, `refseq_id` |

### Functional Annotation

| Type | Description | Key Fields |
|------|-------------|------------|
| [TranscriptConsequence](#type-transcriptconsequence) |  | `consequence_terms`, `domains`, `gene_id` |
| [VariantInSilicoPredictor](#type-variantinsilicopredictor) |  | `id`, `value`, `flags` |
| [LoFCuration](#type-lofcuration) |  | `gene_id`, `gene_version`, `gene_symbol` |
| [LoFCurationInGene](#type-lofcurationingene) |  | `verdict`, `flags` |
| [MultiNucleotideVariantConsequence](#type-multinucleotidevariantconsequence) |  | `gene_id`, `gene_name`, `transcript_id` |
| [StructuralVariantConsequence](#type-structuralvariantconsequence) |  | `consequence`, `genes` |

### Clinical & Disease Data

| Type | Description | Key Fields |
|------|-------------|------------|
| [ClinVarVariant](#type-clinvarvariant) |  | `variant_id`, `reference_genome`, `chrom` |
| [ClinVarVariantDetails](#type-clinvarvariantdetails) |  | `variant_id`, `reference_genome`, `chrom` |
| [ClinVarCondition](#type-clinvarcondition) |  | `name`, `medgen_id` |
| [ClinVarSubmission](#type-clinvarsubmission) |  | `clinical_significance`, `last_evaluated`, `review_status` |
| [ClinVarVariantGnomadData](#type-clinvarvariantgnomaddata) |  | `exome`, `genome` |

### Constraint & Conservation

| Type | Description | Key Fields |
|------|-------------|------------|
| [GnomadConstraint](#type-gnomadconstraint) |  | `exp_lof`, `exp_mis`, `exp_syn` |
| [ExacConstraint](#type-exacconstraint) |  | `exp_syn`, `exp_mis`, `exp_lof` |
| [GnomadV2RegionalMissenseConstraint](#type-gnomadv2regionalmissenseconstraint) |  | `has_no_rmc_evidence`, `passed_qc`, `regions` |
| [GnomadV2RegionalMissenseConstraintRegion](#type-gnomadv2regionalmissenseconstraintregion) |  | `chrom`, `start`, `stop` |
| [MitochondrialRegionConstraint](#type-mitochondrialregionconstraint) |  | `start`, `stop`, `oe` |
| [NonCodingConstraintRegion](#type-noncodingconstraintregion) |  | `chrom`, `start`, `stop` |

### Quality Metrics

| Type | Description | Key Fields |
|------|-------------|------------|
| [VariantSiteQualityMetric](#type-variantsitequalitymetric) |  | `metric`, `value` |
| [VariantGenotypeQuality](#type-variantgenotypequality) |  | `all`, `alt` |
| [VariantGenotypeDepth](#type-variantgenotypedepth) |  | `all`, `alt` |
| [VariantAlleleBalance](#type-variantallelebalance) |  | `alt` |
| [MitochondrialVariantGenotypeQualityMetric](#type-mitochondrialvariantgenotypequalitymetric) |  | `name`, `all`, `alt` |
| [MitochondrialVariantSiteQualityMetric](#type-mitochondrialvariantsitequalitymetric) |  | `name`, `value` |

### Coverage Data

| Type | Description | Key Fields |
|------|-------------|------------|
| [Coverage](#type-coverage) |  | `mean`, `median`, `over_1` |
| [VariantCoverage](#type-variantcoverage) |  | `exome`, `genome` |
| [CoverageBin](#type-coveragebin) |  | `pos`, `mean`, `median` |
| [FeatureCoverage](#type-featurecoverage) |  | `exome`, `genome` |
| [RegionCoverage](#type-regioncoverage) |  | `exome`, `genome` |
| [MitochondrialCoverageBin](#type-mitochondrialcoveragebin) |  | `pos`, `mean`, `median` |
| [CNVTrackCallableCoverageBin](#type-cnvtrackcallablecoveragebin) |  | `xpos`, `percent_callable` |

### Expression & Tissue Data

| Type | Description | Key Fields |
|------|-------------|------------|
| [GtexTissue](#type-gtextissue) |  | `tissue`, `value` |
| [PextRegion](#type-pextregion) |  | `start`, `stop`, `mean` |
| [PextRegionTissue](#type-pextregiontissue) |  | `tissue`, `value` |
| [Pext](#type-pext) |  | `regions`, `flags` |

### Search & Utility Types

| Type | Description | Key Fields |
|------|-------------|------------|
| [VariantSearchResult](#type-variantsearchresult) |  | `variant_id` |
| [GeneSearchResult](#type-genesearchresult) |  | `ensembl_id`, `ensembl_version`, `symbol` |
| [LiftoverVariant](#type-liftovervariant) |  | `variant_id`, `reference_genome` |
| [LiftoverResult](#type-liftoverresult) |  | `source`, `liftover`, `datasets` |
| [Region](#type-region) |  | `reference_genome`, `chrom`, `start` |
| [BrowserMetadata](#type-browsermetadata) |  | `clinvar_release_date` |

### Statistical & Analysis Types

| Type | Description | Key Fields |
|------|-------------|------------|
| [VariantCooccurrence](#type-variantcooccurrence) |  | `variant_ids`, `genotype_counts`, `haplotype_counts` |
| [VariantCooccurrenceInPopulation](#type-variantcooccurrenceinpopulation) |  | `id`, `genotype_counts`, `haplotype_counts` |
| [HeterozygousVariantCooccurrenceCounts](#type-heterozygousvariantcooccurrencecounts) |  | `csq`, `af_cutoff`, `data` |
| [HomozygousVariantCooccurrenceCounts](#type-homozygousvariantcooccurrencecounts) |  | `csq`, `af_cutoff`, `data` |
| [ContingencyTableTest](#type-contingencytabletest) |  | `p_value`, `odds_ratio` |
| [CochranMantelHaenszelTest](#type-cochranmantelhaenszeltest) |  | `chisq`, `p_value` |

### Variant Alliance Types

| Type | Description | Key Fields |
|------|-------------|------------|
| [VAAllele](#type-vaallele) |  | `type`, `location` |
| [VACohort](#type-vacohort) |  | `id`, `label`, `characteristics` |
| [VACohortAlleleFrequency](#type-vacohortallelefrequency) | A measure of the frequency of an Allele in a cohort. | `exome`, `genome` |
| [VASequenceLocation](#type-vasequencelocation) |  | `type`, `sequence_id` |
| [VAQualityMeasures](#type-vaqualitymeasures) |  | `meanDepth`, `fractionCoverage20x`, `qcFilters` |
| [VAAncillaryResults](#type-vaancillaryresults) |  | `grpMaxFAF95`, `jointGrpMaxFAF95`, `homozygotes` |

### Short Tandem Repeats

| Type | Description | Key Fields |
|------|-------------|------------|
| [ShortTandemRepeat](#type-shorttandemrepeat) |  | `id`, `gene`, `associated_diseases` |
| [ShortTandemRepeatDetails](#type-shorttandemrepeatdetails) |  | `id`, `gene`, `associated_diseases` |
| [ShortTandemRepeatGene](#type-shorttandemrepeatgene) |  | `ensembl_id`, `symbol`, `region` |
| [ShortTandemRepeatAssociatedDisease](#type-shorttandemrepeatassociateddisease) |  | `name`, `symbol`, `omim_id` |
| [ShortTandemRepeatReferenceRegion](#type-shorttandemrepeatreferenceregion) |  | `reference_genome`, `chrom`, `start` |

### Histogram & Distribution Types

| Type | Description | Key Fields |
|------|-------------|------------|
| [Histogram](#type-histogram) |  | `bin_edges`, `bin_freq`, `n_larger` |
| [VariantAgeDistribution](#type-variantagedistribution) |  | `het`, `hom` |
| [MitochondrialVariantAgeDistribution](#type-mitochondrialvariantagedistribution) |  | `het`, `hom` |
| [StructuralVariantAgeDistribution](#type-structuralvariantagedistribution) |  | `het`, `hom` |

---

## Enumerations

### `CopyNumberVariantDatasetId`

| Value | Description |
|-------|-------------|
| `gnomad_cnv_r4` | None |

### `DatasetId`

| Value | Description |
|-------|-------------|
| `gnomad_r4` | None |
| `gnomad_r4_non_ukb` | None |
| `gnomad_r3` | None |
| `gnomad_r3_controls_and_biobanks` | None |
| `gnomad_r3_non_cancer` | None |
| `gnomad_r3_non_neuro` | None |
| `gnomad_r3_non_topmed` | None |
| `gnomad_r3_non_v2` | None |
| `gnomad_r2_1` | None |
| `gnomad_r2_1_controls` | None |
| `gnomad_r2_1_non_neuro` | None |
| `gnomad_r2_1_non_cancer` | None |
| `gnomad_r2_1_non_topmed` | None |
| `exac` | None |

### `ReferenceGenomeId`

| Value | Description |
|-------|-------------|
| `GRCh37` | None |
| `GRCh38` | None |

### `StructuralVariantDatasetId`

| Value | Description |
|-------|-------------|
| `gnomad_sv_r2_1` | None |
| `gnomad_sv_r2_1_controls` | None |
| `gnomad_sv_r2_1_non_neuro` | None |
| `gnomad_sv_r4` | None |

### `VAComparator`

| Value | Description |
|-------|-------------|
| `LTE` | None |
| `GTE` | None |

---

## Best Practices

### 1. Request Only Needed Fields
```graphql
# ❌ Bad - requests all fields
query {
  variant(variantId: "1-55516888-G-A", dataset: gnomad_r4) {
    ... on VariantDetails  # Don't use fragments for everything
  }
}

# ✅ Good - requests only needed fields
query {
  variant(variantId: "1-55516888-G-A", dataset: gnomad_r4) {
    variant_id
    genome { af }
  }
}
```

### 2. Use Appropriate Datasets
- For GRCh38: Use `gnomad_r4` (latest) or `gnomad_r3`
- For GRCh37: Use `gnomad_r2_1`
- Match dataset to your reference genome

### 3. Handle Errors Gracefully
- Check for `errors` in response
- Handle null results (variant not found)
- Implement timeout handling

### 4. Variant ID Format
- Format: `chromosome-position-reference-alternate`
- Example: `1-55516888-G-A`
- Chromosome can be 1-22, X, Y, or MT

---

*For more examples, see the [Query Cookbook](gnomad_query_cookbook.md)*