# gnomAD Type Reference

This document provides detailed information about all data types in the gnomAD GraphQL API.

## Table of Contents

- [Core Variant Types](#core-variant-types)
- [Specialized Variant Types](#specialized-variant-types)
- [Population & Frequency Data](#population-and-frequency-data)
- [Gene & Transcript Types](#gene-and-transcript-types)
- [Functional Annotation](#functional-annotation)
- [Clinical & Disease Data](#clinical-and-disease-data)
- [Constraint & Conservation](#constraint-and-conservation)
- [Quality Metrics](#quality-metrics)
- [Coverage Data](#coverage-data)
- [Expression & Tissue Data](#expression-and-tissue-data)
- [Search & Utility Types](#search-and-utility-types)
- [Statistical & Analysis Types](#statistical-and-analysis-types)
- [Variant Alliance Types](#variant-alliance-types)
- [Short Tandem Repeats](#short-tandem-repeats)
- [Histogram & Distribution Types](#histogram-and-distribution-types)

---

## Core Variant Types

### <a id="type-variant"></a>`Variant`

**Used by:** `Gene.variants`, `Region.variants`, `Transcript.variants`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| alt | `String!` | - |
| chrom | `String!` | - |
| domains | `[String!]` | - |
| flags | `[String!]` | - |
| in_silico_predictors | `[VariantInSilicoPredictor!]` | - |
| pos | `Int!` | - |
| ref | `String!` | - |
| reference_genome | `ReferenceGenomeId!` | - |
| rsids | `[String!]` | - |
| va | `VACohortAlleleFrequency!` | GA4GH-format data |
| variantId | `String!` | Deprecated - replaced by snake case versions Preserved for compatibility with existing browser queries |
| **variant_id** | `String!` | - |
| consequence | `String` | Deprecated - Use transcript_consequences[0] instead Preserved for compatibility with existing browser queries |
| consequence_in_canonical_transcript | `Boolean` | - |
| exome | `VariantSequencingTypeData` | - |
| faf95_joint | `VariantFilteringAlleleFrequency` | - |
| faf99_joint | `VariantFilteringAlleleFrequency` | - |
| **gene_id** | `String` | - |
| gene_symbol | `String` | - |
| genome | `VariantSequencingTypeData` | - |
| hgvs | `String` | Deprecated - use hgvsp and hgvsc instead |
| hgvsc | `String` | - |
| hgvsp | `String` | - |
| joint | `VariantJointSequencingTypeData` | - |
| lof | `String` | - |
| lof_curation | `LoFCurationInGene` | - |
| lof_filter | `String` | - |
| lof_flags | `String` | - |
| rsid | `String` | Deprecated - use rsids |
| transcript_consequence | `TranscriptConsequence` | - |
| **transcript_id** | `String` | - |
| transcript_version | `String` | - |
| vrs | `VAAllele` | - |

</details>

### <a id="type-variantdetails"></a>`VariantDetails`

**Used by:** `Query.variant`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| alt | `String!` | - |
| chrom | `String!` | - |
| colocatedVariants | `[String!]!` | - |
| colocated_variants | `[String!]!` | - |
| coverage | `VariantCoverage!` | - |
| flags | `[String!]` | - |
| in_silico_predictors | `[VariantInSilicoPredictor!]` | - |
| lof_curations | `[LoFCuration!]` | - |
| multiNucleotideVariants | `[MultiNucleotideVariantSummary!]` | - |
| multi_nucleotide_variants | `[MultiNucleotideVariantSummary!]` | - |
| pos | `Int!` | - |
| ref | `String!` | - |
| reference_genome | `ReferenceGenomeId!` | - |
| rsids | `[String!]` | - |
| sortedTranscriptConsequences | `[TranscriptConsequence!]` | - |
| transcript_consequences | `[TranscriptConsequence!]` | - |
| va | `VACohortAlleleFrequency!` | - |
| variantId | `String!` | Deprecated - replaced by snake case versions Preserved for compatibility with existing browser queries |
| **variant_id** | `String!` | - |
| caid | `String` | - |
| exome | `VariantDetailsSequencingTypeData` | - |
| genome | `VariantDetailsSequencingTypeData` | - |
| joint | `VariantDetailsJointSequencingTypeData` | - |
| non_coding_constraint | `NonCodingConstraintRegion` | - |
| rsid | `String` | Deprecated - use rsids |
| vrs | `VAAllele` | - |

</details>

### <a id="type-variantsequencingtypedata"></a>`VariantSequencingTypeData`

**Used by:** `Variant.exome`, `Variant.genome`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| filters | `[String!]` | - |
| flags | `[String!]` | - |
| **ac** | `Int` | - |
| ac_hemi | `Int` | - |
| ac_hom | `Int` | Deprecated - replaced by homozygote/hemizygote count |
| **af** | `Float` | Deprecated - calculate from AC and AN Preserved for compatibility with existing browser queries |
| **an** | `Int` | - |
| faf95 | `VariantFilteringAlleleFrequency` | - |
| fafmax | `Fafmax` | - |
| hemizygote_count | `Int` | - |
| homozygote_count | `Int` | - |
| populations | `[VariantPopulation]` | - |

</details>

### <a id="type-variantjointsequencingtypedata"></a>`VariantJointSequencingTypeData`

**Used by:** `Variant.joint`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| filters | `[String!]` | - |
| **ac** | `Int` | - |
| **an** | `Int` | - |
| fafmax | `Fafmax` | - |
| hemizygote_count | `Int` | - |
| homozygote_count | `Int` | - |
| populations | `[VariantPopulation]` | - |

</details>

### <a id="type-variantqualitymetrics"></a>`VariantQualityMetrics`

**Used by:** `VariantDetailsSequencingTypeData.quality_metrics`, `VariantDetailsSequencingTypeData.qualityMetrics`, `VariantDetailsJointSequencingTypeData.quality_metrics`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| siteQualityMetrics | `[VariantSiteQualityMetric!]!` | - |
| site_quality_metrics | `[VariantSiteQualityMetric!]!` | - |
| alleleBalance | `VariantAlleleBalance` | Deprecated - replaced by snake case versions |
| allele_balance | `VariantAlleleBalance` | - |
| genotypeDepth | `VariantGenotypeDepth` | - |
| genotypeQuality | `VariantGenotypeQuality` | - |
| genotype_depth | `VariantGenotypeDepth` | - |
| genotype_quality | `VariantGenotypeQuality` | - |

</details>

## Specialized Variant Types

### <a id="type-mitochondrialvariant"></a>`MitochondrialVariant`

**Used by:** `Gene.mitochondrial_variants`, `Region.mitochondrial_variants`, `Transcript.mitochondrial_variants`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| filters | `[String!]` | - |
| flags | `[String!]` | - |
| pos | `Int!` | - |
| reference_genome | `ReferenceGenomeId!` | - |
| rsids | `[String!]` | - |
| **variant_id** | `String!` | - |
| ac_het | `Int` | - |
| ac_hom | `Int` | - |
| **an** | `Int` | - |
| consequence | `String` | - |
| **gene_id** | `String` | - |
| gene_symbol | `String` | - |
| hgvsc | `String` | - |
| hgvsp | `String` | - |
| lof | `String` | - |
| lof_filter | `String` | - |
| lof_flags | `String` | - |
| max_heteroplasmy | `Float` | - |
| rsid | `String` | - |
| **transcript_id** | `String` | - |

</details>

### <a id="type-mitochondrialvariantdetails"></a>`MitochondrialVariantDetails`

**Used by:** `Query.mitochondrial_variant`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| alt | `String!` | - |
| filters | `[String!]` | - |
| flags | `[String!]!` | - |
| genotype_quality_filters | `[MitochondrialVariantGenotypeQualityFilter!]` | - |
| genotype_quality_metrics | `[MitochondrialVariantGenotypeQualityMetric!]` | - |
| haplogroups | `[MitochondrialVariantHaplogroup!]` | - |
| populations | `[MitochondrialVariantPopulation!]!` | - |
| pos | `Int!` | - |
| ref | `String!` | - |
| reference_genome | `ReferenceGenomeId!` | - |
| transcript_consequences | `[TranscriptConsequence!]` | - |
| **variant_id** | `String!` | - |
| ac_het | `Int` | - |
| ac_hom | `Int` | - |
| ac_hom_mnv | `Int` | - |
| age_distribution | `MitochondrialVariantAgeDistribution` | - |
| **an** | `Int` | - |
| excluded_ac | `Int` | - |
| haplogroup_defining | `Boolean` | - |
| heteroplasmy_distribution | `Histogram` | - |
| max_heteroplasmy | `Float` | - |
| mitotip_score | `Float` | - |
| mitotip_trna_prediction | `String` | - |
| pon_ml_probability_of_pathogenicity | `Float` | - |
| pon_mt_trna_prediction | `String` | - |
| rsid | `String` | - |
| rsids | `[String]` | - |
| site_quality_metrics | `[MitochondrialVariantSiteQualityMetric]` | - |

</details>

### <a id="type-structuralvariant"></a>`StructuralVariant`

**Used by:** `Gene.structural_variants`, `Region.structural_variants`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| **ac** | `Int!` | - |
| **af** | `Float!` | - |
| **an** | `Int!` | - |
| chrom | `String!` | - |
| end | `Int!` | - |
| filters | `[String!]` | - |
| pos | `Int!` | - |
| reference_genome | `ReferenceGenomeId!` | - |
| **variant_id** | `String!` | - |
| ac_hemi | `Int` | - |
| ac_hom | `Int` | Deprecated - replaced by homozygote/hemizygote count |
| chrom2 | `String` | - |
| consequence | `String` | Deprecated - replaced by major_consequence |
| end2 | `Int` | - |
| hemizygote_count | `Int` | - |
| homozygote_count | `Int` | - |
| length | `Int` | - |
| major_consequence | `String` | - |
| pos2 | `Int` | - |
| type | `String` | - |

</details>

### <a id="type-structuralvariantdetails"></a>`StructuralVariantDetails`

**Used by:** `Query.structural_variant`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| **ac** | `Int!` | - |
| **af** | `Float!` | - |
| algorithms | `[String!]` | - |
| alts | `[String!]` | - |
| **an** | `Int!` | - |
| chrom | `String!` | - |
| consequences | `[StructuralVariantConsequence!]` | - |
| copy_numbers | `[StructuralVariantCopyNumber!]` | - |
| cpx_intervals | `[String!]` | - |
| end | `Int!` | - |
| evidence | `[String!]` | - |
| filters | `[String!]` | - |
| genes | `[String!]` | - |
| populations | `[StructuralVariantPopulation!]` | - |
| pos | `Int!` | - |
| reference_genome | `ReferenceGenomeId!` | - |
| **variant_id** | `String!` | - |
| ac_hemi | `Int` | - |
| ac_hom | `Int` | Deprecated - replaced by homozygote/hemizygote count |
| age_distribution | `StructuralVariantAgeDistribution` | - |
| chrom2 | `String` | - |
| consequence | `String` | Deprecated - replaced by major_consequence |
| cpx_type | `String` | - |
| end2 | `Int` | - |
| genotype_quality | `StructuralVariantGenotypeQuality` | - |
| hemizygote_count | `Int` | - |
| homozygote_count | `Int` | - |
| length | `Int` | - |
| major_consequence | `String` | - |
| pos2 | `Int` | - |
| qual | `Float` | - |
| type | `String` | - |

</details>

### <a id="type-copynumbervariant"></a>`CopyNumberVariant`

**Used by:** `Gene.copy_number_variants`, `Region.copy_number_variants`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| chrom | `String!` | - |
| end | `Int!` | - |
| filters | `[String!]` | - |
| pos | `Int!` | - |
| reference_genome | `ReferenceGenomeId!` | - |
| sc | `Float!` | - |
| sf | `Float!` | - |
| sn | `Float!` | - |
| **variant_id** | `String!` | - |
| endmax | `Int` | - |
| endmin | `Int` | - |
| length | `Int` | - |
| posmax | `Int` | - |
| posmin | `Int` | - |
| type | `String` | - |

</details>

### <a id="type-copynumbervariantdetails"></a>`CopyNumberVariantDetails`

**Used by:** `Query.copy_number_variant`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| alts | `[String!]` | - |
| chrom | `String!` | - |
| end | `Int!` | - |
| filters | `[String!]` | - |
| genes | `[String!]` | - |
| populations | `[CopyNumberVariantPopulation!]` | - |
| pos | `Int!` | - |
| reference_genome | `ReferenceGenomeId!` | - |
| sc | `Float!` | - |
| sf | `Float!` | - |
| sn | `Float!` | - |
| **variant_id** | `String!` | - |
| endmax | `Int` | - |
| endmin | `Int` | - |
| length | `Int` | - |
| posmax | `Int` | - |
| posmin | `Int` | - |
| qual | `Float` | - |
| type | `String` | - |

</details>

### <a id="type-multinucleotidevariantdetails"></a>`MultiNucleotideVariantDetails`

**Used by:** `Query.multiNucleotideVariant`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| alt | `String!` | - |
| chrom | `String!` | - |
| consequences | `[MultiNucleotideVariantConsequence!]` | - |
| constituent_snvs | `[MultiNucleotideVariantConstituentSNV!]` | - |
| pos | `Int!` | - |
| ref | `String!` | - |
| reference_genome | `ReferenceGenomeId!` | - |
| related_mnvs | `[MultiNucleotideVariantSummary!]!` | - |
| **variant_id** | `String!` | - |
| exome | `MultiNucleotideVariantDetailsSequencingData` | - |
| genome | `MultiNucleotideVariantDetailsSequencingData` | - |

</details>

## Population & Frequency Data

### <a id="type-variantpopulation"></a>`VariantPopulation`

**Used by:** `VariantSequencingTypeData.populations`, `VariantJointSequencingTypeData.populations`, `VariantDetailsSequencingTypeData.populations`
 and 1 more...

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| **ac** | `Int!` | - |
| ac_hom | `Int!` | Deprecated - replaced by homozygote/hemizygote count |
| **an** | `Int!` | - |
| homozygote_count | `Int!` | - |
| id | `String!` | - |
| ac_hemi | `Int` | - |
| hemizygote_count | `Int` | - |

</details>

### <a id="type-variantfilteringallelefrequency"></a>`VariantFilteringAlleleFrequency`

**Used by:** `VariantSequencingTypeData.faf95`, `Variant.faf95_joint`, `Variant.faf99_joint`
 and 4 more...

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| popmax | `Float` | - |
| popmax_population | `String` | - |

</details>

### <a id="type-variantlocalancestrypopulation"></a>`VariantLocalAncestryPopulation`

**Used by:** `VariantDetailsSequencingTypeData.local_ancestry_populations`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| **ac** | `Int!` | - |
| **an** | `Int!` | - |
| id | `String!` | - |

</details>

### <a id="type-mitochondrialvariantpopulation"></a>`MitochondrialVariantPopulation`

**Used by:** `MitochondrialVariantDetails.populations`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| ac_het | `Int!` | - |
| ac_hom | `Int!` | - |
| **an** | `Int!` | - |
| heteroplasmy_distribution | `Histogram!` | - |
| id | `String!` | - |

</details>

### <a id="type-structuralvariantpopulation"></a>`StructuralVariantPopulation`

**Used by:** `StructuralVariantDetails.populations`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| **ac** | `Int!` | - |
| **an** | `Int!` | - |
| id | `String!` | - |
| ac_hemi | `Int` | Deprecated - replaced by homozygote/hemizygote count |
| ac_hom | `Int` | - |
| hemizygote_count | `Int` | - |
| homozygote_count | `Int` | - |

</details>

### <a id="type-copynumbervariantpopulation"></a>`CopyNumberVariantPopulation`

**Used by:** `CopyNumberVariantDetails.populations`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| id | `String!` | - |
| sc | `Float!` | - |
| sf | `Float!` | - |
| sn | `Float!` | - |

</details>

### <a id="type-fafmax"></a>`Fafmax`

**Used by:** `VariantSequencingTypeData.fafmax`, `VariantJointSequencingTypeData.fafmax`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| faf95_max | `Float` | - |
| faf95_max_gen_anc | `String` | - |
| faf99_max | `Float` | - |
| faf99_max_gen_anc | `String` | - |

</details>

### <a id="type-vagrpmaxfaf95"></a>`VAGrpMaxFAF95`

**Used by:** `VAAncillaryResults.grpMaxFAF95`, `VAAncillaryResults.jointGrpMaxFAF95`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| confidenceInterval | `Float!` | - |
| frequency | `Float!` | - |
| groupId | `String!` | - |

</details>

## Gene & Transcript Types

### <a id="type-gene"></a>`Gene`

**Used by:** `Query.gene`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| chrom | `String!` | - |
| clinvar_variants | `[ClinVarVariant!]` | - |
| cnv_track_callable_coverage | `[CNVTrackCallableCoverageBin!]` | - |
| copy_number_variants | `[CopyNumberVariant!]!` | - |
| coverage | `FeatureCoverage!` | - |
| exac_regional_missense_constraint_regions | `[ExacRegionalMissenseConstraintRegion!]` | - |
| exons | `[Exon!]!` | - |
| flags | `[String!]!` | - |
| gencode_symbol | `String!` | - |
| **gene_id** | `String!` | - |
| gene_version | `String!` | - |
| heterozygous_variant_cooccurrence_counts | `[HeterozygousVariantCooccurrenceCounts!]!` | - |
| homozygous_variant_cooccurrence_counts | `[HomozygousVariantCooccurrenceCounts!]!` | - |
| mitochondrial_coverage | `[MitochondrialCoverageBin!]` | - |
| mitochondrial_variants | `[MitochondrialVariant!]!` | - |
| reference_genome | `ReferenceGenomeId!` | - |
| short_tandem_repeats | `[ShortTandemRepeat!]!` | - |
| start | `Int!` | - |
| stop | `Int!` | - |
| strand | `String!` | - |
| structural_variants | `[StructuralVariant!]!` | - |
| symbol | `String!` | - |
| transcripts | `[GeneTranscript!]!` | - |
| variants | `[Variant!]!` | - |
| canonical_transcript_id | `String` | - |
| exac_constraint | `ExacConstraint` | - |
| gnomad_constraint | `GnomadConstraint` | - |
| gnomad_v2_regional_missense_constraint | `GnomadV2RegionalMissenseConstraint` | - |
| hgnc_id | `String` | - |
| mane_select_transcript | `ManeSelectTranscript` | - |
| mitochondrial_constraint | `MitochondrialGeneConstraint` | - |
| mitochondrial_missense_constraint_regions | `[MitochondrialRegionConstraint]` | - |
| name | `String` | - |
| ncbi_id | `String` | - |
| omim_id | `String` | - |
| pext | `Pext` | - |

</details>

### <a id="type-transcript"></a>`Transcript`

**Used by:** `Query.transcript`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| chrom | `String!` | - |
| clinvar_variants | `[ClinVarVariant!]` | - |
| coverage | `FeatureCoverage!` | - |
| exons | `[Exon!]!` | - |
| gene | `TranscriptGene!` | - |
| **gene_id** | `String!` | - |
| mitochondrial_coverage | `[MitochondrialCoverageBin!]` | - |
| mitochondrial_variants | `[MitochondrialVariant!]!` | - |
| reference_genome | `ReferenceGenomeId!` | - |
| start | `Int!` | - |
| stop | `Int!` | - |
| strand | `String!` | - |
| **transcript_id** | `String!` | - |
| transcript_version | `String!` | - |
| variants | `[Variant!]!` | - |
| exac_constraint | `ExacConstraint` | - |
| gnomad_constraint | `GnomadConstraint` | - |
| gtex_tissue_expression | `[GtexTissue]` | - |

</details>

### <a id="type-exon"></a>`Exon`

**Used by:** `GeneTranscript.exons`, `Gene.exons`, `RegionGeneTranscript.exons`
 and 3 more...

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| feature_type | `String!` | - |
| start | `Int!` | - |
| stop | `Int!` | - |

</details>

### <a id="type-genetranscript"></a>`GeneTranscript`

**Used by:** `Gene.transcripts`, `TranscriptGene.transcripts`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| chrom | `String!` | - |
| exons | `[Exon!]!` | - |
| gtex_tissue_expression | `[GtexTissue!]` | - |
| reference_genome | `ReferenceGenomeId!` | - |
| start | `Int!` | - |
| stop | `Int!` | - |
| strand | `String!` | - |
| **transcript_id** | `String!` | - |
| transcript_version | `String!` | - |

</details>

### <a id="type-transcriptgene"></a>`TranscriptGene`

**Used by:** `Transcript.gene`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| chrom | `String!` | - |
| exac_regional_missense_constraint_regions | `[ExacRegionalMissenseConstraintRegion!]` | - |
| exons | `[Exon!]!` | - |
| flags | `[String!]!` | - |
| **gene_id** | `String!` | - |
| gene_version | `String!` | - |
| reference_genome | `ReferenceGenomeId!` | - |
| start | `Int!` | - |
| stop | `Int!` | - |
| strand | `String!` | - |
| symbol | `String!` | - |
| transcripts | `[GeneTranscript!]!` | - |
| canonical_transcript_id | `String` | - |
| exac_constraint | `ExacConstraint` | - |
| gnomad_constraint | `GnomadConstraint` | - |
| hgnc_id | `String` | - |
| mane_select_transcript | `ManeSelectTranscript` | - |
| name | `String` | - |
| ncbi_id | `String` | - |
| omim_id | `String` | - |
| pext | `Pext` | - |

</details>

### <a id="type-regiongene"></a>`RegionGene`

**Used by:** `Region.genes`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| exons | `[Exon!]!` | - |
| **gene_id** | `String!` | - |
| start | `Int!` | - |
| stop | `Int!` | - |
| symbol | `String!` | - |
| transcripts | `[RegionGeneTranscript!]!` | - |

</details>

### <a id="type-regiongenetranscript"></a>`RegionGeneTranscript`

**Used by:** `RegionGene.transcripts`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| exons | `[Exon!]!` | - |
| start | `Int!` | - |
| stop | `Int!` | - |
| **transcript_id** | `String!` | - |

</details>

### <a id="type-maneselecttranscript"></a>`ManeSelectTranscript`

**Used by:** `Gene.mane_select_transcript`, `TranscriptGene.mane_select_transcript`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| ensembl_id | `String!` | - |
| ensembl_version | `String!` | - |
| refseq_id | `String!` | - |
| refseq_version | `String!` | - |

</details>

## Functional Annotation

### <a id="type-transcriptconsequence"></a>`TranscriptConsequence`

**Used by:** `MitochondrialVariantDetails.transcript_consequences`, `Variant.transcript_consequence`, `VariantDetails.transcript_consequences`
 and 1 more...

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| consequence_terms | `[String!]` | - |
| domains | `[String!]` | - |
| **gene_id** | `String!` | - |
| **transcript_id** | `String!` | - |
| canonical | `Boolean` | Deprecated - replaced by is_canonical |
| gene_symbol | `String` | - |
| gene_version | `String` | - |
| hgvs | `String` | - |
| hgvsc | `String` | - |
| hgvsp | `String` | - |
| is_canonical | `Boolean` | - |
| is_mane_select | `Boolean` | - |
| is_mane_select_version | `Boolean` | - |
| lof | `String` | - |
| lof_filter | `String` | - |
| lof_flags | `String` | - |
| major_consequence | `String` | - |
| polyphen_prediction | `String` | - |
| refseq_id | `String` | - |
| refseq_version | `String` | - |
| sift_prediction | `String` | - |
| transcript_version | `String` | - |

</details>

### <a id="type-variantinsilicopredictor"></a>`VariantInSilicoPredictor`

**Used by:** `Variant.in_silico_predictors`, `VariantDetails.in_silico_predictors`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| flags | `[String!]!` | - |
| id | `String!` | - |
| value | `String!` | - |

</details>

### <a id="type-lofcuration"></a>`LoFCuration`

**Used by:** `VariantDetails.lof_curations`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| flags | `[String!]` | - |
| **gene_id** | `String!` | - |
| gene_version | `String!` | - |
| project | `String!` | - |
| verdict | `String!` | - |
| gene_symbol | `String` | - |

</details>

### <a id="type-lofcurationingene"></a>`LoFCurationInGene`

**Used by:** `Variant.lof_curation`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| flags | `[String!]` | - |
| verdict | `String!` | - |

</details>

### <a id="type-multinucleotidevariantconsequence"></a>`MultiNucleotideVariantConsequence`

**Used by:** `MultiNucleotideVariantDetails.consequences`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| amino_acids | `String!` | - |
| codons | `String!` | - |
| consequence | `String!` | - |
| **gene_id** | `String!` | - |
| gene_name | `String!` | - |
| snv_consequences | `[MultiNucleotideVariantConstituentSNVConsequence!]!` | - |
| **transcript_id** | `String!` | - |
| category | `String` | - |

</details>

### <a id="type-structuralvariantconsequence"></a>`StructuralVariantConsequence`

**Used by:** `StructuralVariantDetails.consequences`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| consequence | `String!` | - |
| genes | `[String!]` | - |

</details>

## Clinical & Disease Data

### <a id="type-clinvarvariant"></a>`ClinVarVariant`

**Used by:** `Gene.clinvar_variants`, `Region.clinvar_variants`, `Transcript.clinvar_variants`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| alt | `String!` | - |
| chrom | `String!` | - |
| clinical_significance | `String!` | - |
| clinvar_variation_id | `String!` | - |
| gold_stars | `Int!` | - |
| pos | `Int!` | - |
| ref | `String!` | - |
| reference_genome | `ReferenceGenomeId!` | - |
| review_status | `String!` | - |
| **variant_id** | `String!` | - |
| gnomad | `ClinVarVariantGnomadData` | - |
| hgvsc | `String` | - |
| hgvsp | `String` | - |
| in_gnomad | `Boolean` | - |
| major_consequence | `String` | - |
| **transcript_id** | `String` | - |

</details>

### <a id="type-clinvarvariantdetails"></a>`ClinVarVariantDetails`

**Used by:** `Query.clinvar_variant`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| alt | `String!` | - |
| chrom | `String!` | - |
| clinical_significance | `String!` | - |
| clinvar_variation_id | `String!` | - |
| gold_stars | `Int!` | - |
| in_gnomad | `Boolean!` | - |
| pos | `Int!` | - |
| ref | `String!` | - |
| reference_genome | `ReferenceGenomeId!` | - |
| review_status | `String!` | - |
| submissions | `[ClinVarSubmission!]!` | - |
| **variant_id** | `String!` | - |
| gnomad | `ClinVarVariantGnomadData` | - |
| last_evaluated | `String` | - |
| rsid | `String` | - |

</details>

### <a id="type-clinvarcondition"></a>`ClinVarCondition`

**Used by:** `ClinVarSubmission.conditions`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| name | `String!` | - |
| medgen_id | `String` | - |

</details>

### <a id="type-clinvarsubmission"></a>`ClinVarSubmission`

**Used by:** `ClinVarVariantDetails.submissions`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| conditions | `[ClinVarCondition!]!` | - |
| review_status | `String!` | - |
| submitter_name | `String!` | - |
| clinical_significance | `String` | - |
| last_evaluated | `String` | - |

</details>

### <a id="type-clinvarvariantgnomaddata"></a>`ClinVarVariantGnomadData`

**Used by:** `ClinVarVariant.gnomad`, `ClinVarVariantDetails.gnomad`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| exome | `ClinVarVariantGnomadSequencingTypeData` | - |
| genome | `ClinVarVariantGnomadSequencingTypeData` | - |

</details>

## Constraint & Conservation

### <a id="type-gnomadconstraint"></a>`GnomadConstraint`

**Used by:** `Gene.gnomad_constraint`, `TranscriptGene.gnomad_constraint`, `Transcript.gnomad_constraint`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| exp_mis | `Float!` | - |
| flags | `[String!]` | - |
| mis_z | `Float!` | - |
| oe_mis | `Float!` | - |
| syn_z | `Float!` | - |
| exp_lof | `Float` | - |
| exp_syn | `Float` | - |
| lof_z | `Float` | - |
| obs_lof | `Int` | - |
| obs_mis | `Int` | - |
| obs_syn | `Int` | - |
| oe_lof | `Float` | - |
| oe_lof_lower | `Float` | - |
| oe_lof_upper | `Float` | - |
| oe_mis_lower | `Float` | - |
| oe_mis_upper | `Float` | - |
| oe_syn | `Float` | - |
| oe_syn_lower | `Float` | - |
| oe_syn_upper | `Float` | - |
| pLI | `Float` | Deprecated fields |
| pli | `Float` | - |

</details>

### <a id="type-exacconstraint"></a>`ExacConstraint`

**Used by:** `Gene.exac_constraint`, `TranscriptGene.exac_constraint`, `Transcript.exac_constraint`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| mis_z | `Float!` | - |
| pLI | `Float!` | Deprecated fields |
| syn_z | `Float!` | - |
| exp_lof | `Float` | - |
| exp_mis | `Float` | - |
| exp_syn | `Float` | - |
| lof_z | `Float` | - |
| mu_lof | `Float` | - |
| mu_mis | `Float` | - |
| mu_syn | `Float` | - |
| obs_lof | `Int` | - |
| obs_mis | `Int` | - |
| obs_syn | `Int` | - |
| pli | `Float` | - |

</details>

### <a id="type-gnomadv2regionalmissenseconstraint"></a>`GnomadV2RegionalMissenseConstraint`

**Used by:** `Gene.gnomad_v2_regional_missense_constraint`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| has_no_rmc_evidence | `Boolean` | - |
| passed_qc | `Boolean` | - |
| regions | `[GnomadV2RegionalMissenseConstraintRegion]` | - |

</details>

### <a id="type-gnomadv2regionalmissenseconstraintregion"></a>`GnomadV2RegionalMissenseConstraintRegion`

**Used by:** `GnomadV2RegionalMissenseConstraint.regions`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| aa_start | `String` | - |
| aa_stop | `String` | - |
| chisq_diff_null | `Float` | - |
| chrom | `String` | - |
| exp_mis | `Float` | - |
| obs_exp | `Float` | - |
| obs_mis | `Int` | - |
| p_value | `Float` | - |
| start | `Int` | - |
| stop | `Int` | - |

</details>

### <a id="type-mitochondrialregionconstraint"></a>`MitochondrialRegionConstraint`

**Used by:** `Gene.mitochondrial_missense_constraint_regions`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| oe | `Float!` | - |
| oe_lower | `Float!` | - |
| oe_upper | `Float!` | - |
| start | `Int!` | - |
| stop | `Int!` | - |

</details>

### <a id="type-noncodingconstraintregion"></a>`NonCodingConstraintRegion`

**Used by:** `Region.non_coding_constraints`, `VariantDetails.non_coding_constraint`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| chrom | `String!` | - |
| element_id | `String!` | - |
| expected | `Float!` | - |
| observed | `Float!` | - |
| oe | `Float!` | - |
| possible | `Float!` | - |
| start | `Int!` | - |
| stop | `Int!` | - |
| z | `Float!` | - |

</details>

## Quality Metrics

### <a id="type-variantsitequalitymetric"></a>`VariantSiteQualityMetric`

**Used by:** `VariantQualityMetrics.site_quality_metrics`, `VariantQualityMetrics.siteQualityMetrics`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| metric | `String!` | - |
| value | `Float` | - |

</details>

### <a id="type-variantgenotypequality"></a>`VariantGenotypeQuality`

**Used by:** `VariantQualityMetrics.genotype_quality`, `VariantQualityMetrics.genotypeQuality`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| all | `Histogram` | - |
| alt | `Histogram` | - |

</details>

### <a id="type-variantgenotypedepth"></a>`VariantGenotypeDepth`

**Used by:** `VariantQualityMetrics.genotype_depth`, `VariantQualityMetrics.genotypeDepth`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| all | `Histogram` | - |
| alt | `Histogram` | - |

</details>

### <a id="type-variantallelebalance"></a>`VariantAlleleBalance`

**Used by:** `VariantQualityMetrics.allele_balance`, `VariantQualityMetrics.alleleBalance`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| alt | `Histogram` | - |

</details>

### <a id="type-mitochondrialvariantgenotypequalitymetric"></a>`MitochondrialVariantGenotypeQualityMetric`

**Used by:** `MitochondrialVariantDetails.genotype_quality_metrics`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| name | `String!` | - |
| all | `Histogram` | - |
| alt | `Histogram` | - |

</details>

### <a id="type-mitochondrialvariantsitequalitymetric"></a>`MitochondrialVariantSiteQualityMetric`

**Used by:** `MitochondrialVariantDetails.site_quality_metrics`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| name | `String!` | - |
| value | `Float` | - |

</details>

## Coverage Data

### <a id="type-coverage"></a>`Coverage`

**Used by:** `VariantCoverage.exome`, `VariantCoverage.genome`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| mean | `Float` | - |
| median | `Float` | - |
| over_1 | `Float` | - |
| over_10 | `Float` | - |
| over_100 | `Float` | - |
| over_15 | `Float` | - |
| over_20 | `Float` | - |
| over_25 | `Float` | - |
| over_30 | `Float` | - |
| over_5 | `Float` | - |
| over_50 | `Float` | - |

</details>

### <a id="type-variantcoverage"></a>`VariantCoverage`

**Used by:** `VariantDetails.coverage`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| exome | `Coverage` | - |
| genome | `Coverage` | - |

</details>

### <a id="type-coveragebin"></a>`CoverageBin`

**Used by:** `FeatureCoverage.exome`, `FeatureCoverage.genome`, `RegionCoverage.exome`
 and 1 more...

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| pos | `Int!` | - |
| mean | `Float` | - |
| median | `Float` | - |
| over_1 | `Float` | - |
| over_10 | `Float` | - |
| over_100 | `Float` | - |
| over_15 | `Float` | - |
| over_20 | `Float` | - |
| over_25 | `Float` | - |
| over_30 | `Float` | - |
| over_5 | `Float` | - |
| over_50 | `Float` | - |

</details>

### <a id="type-featurecoverage"></a>`FeatureCoverage`

**Used by:** `Gene.coverage`, `Transcript.coverage`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| exome | `[CoverageBin!]!` | - |
| genome | `[CoverageBin!]!` | - |

</details>

### <a id="type-regioncoverage"></a>`RegionCoverage`

**Used by:** `Region.coverage`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| exome | `[CoverageBin!]!` | - |
| genome | `[CoverageBin!]!` | - |

</details>

### <a id="type-mitochondrialcoveragebin"></a>`MitochondrialCoverageBin`

**Used by:** `Gene.mitochondrial_coverage`, `Region.mitochondrial_coverage`, `Transcript.mitochondrial_coverage`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| pos | `Float!` | - |
| mean | `Float` | - |
| median | `Float` | - |
| over_100 | `Float` | - |
| over_1000 | `Float` | - |

</details>

### <a id="type-cnvtrackcallablecoveragebin"></a>`CNVTrackCallableCoverageBin`

**Used by:** `Gene.cnv_track_callable_coverage`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| xpos | `Float!` | - |
| percent_callable | `Float` | - |

</details>

## Expression & Tissue Data

### <a id="type-gtextissue"></a>`GtexTissue`

**Used by:** `GeneTranscript.gtex_tissue_expression`, `Transcript.gtex_tissue_expression`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| tissue | `String!` | - |
| value | `Float!` | - |

</details>

### <a id="type-pextregion"></a>`PextRegion`

**Used by:** `Pext.regions`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| mean | `Float!` | - |
| start | `Int!` | - |
| stop | `Int!` | - |
| tissues | `[PextRegionTissue!]!` | - |

</details>

### <a id="type-pextregiontissue"></a>`PextRegionTissue`

**Used by:** `PextRegion.tissues`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| tissue | `String` | - |
| value | `Float` | - |

</details>

### <a id="type-pext"></a>`Pext`

**Used by:** `Gene.pext`, `TranscriptGene.pext`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| flags | `[String!]!` | - |
| regions | `[PextRegion!]!` | - |

</details>

## Search & Utility Types

### <a id="type-variantsearchresult"></a>`VariantSearchResult`

**Used by:** `Query.variant_search`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| **variant_id** | `String!` | - |

</details>

### <a id="type-genesearchresult"></a>`GeneSearchResult`

**Used by:** `Query.gene_search`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| ensembl_id | `String!` | - |
| ensembl_version | `String!` | - |
| symbol | `String` | - |

</details>

### <a id="type-liftovervariant"></a>`LiftoverVariant`

**Used by:** `LiftoverResult.source`, `LiftoverResult.liftover`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| reference_genome | `ReferenceGenomeId!` | - |
| **variant_id** | `String!` | - |

</details>

### <a id="type-liftoverresult"></a>`LiftoverResult`

**Used by:** `Query.liftover`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| datasets | `[String!]!` | - |
| liftover | `LiftoverVariant!` | - |
| source | `LiftoverVariant!` | - |

</details>

### <a id="type-region"></a>`Region`

**Used by:** `Query.region`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| chrom | `String!` | - |
| clinvar_variants | `[ClinVarVariant!]` | - |
| copy_number_variants | `[CopyNumberVariant!]!` | - |
| coverage | `RegionCoverage!` | - |
| genes | `[RegionGene!]!` | - |
| mitochondrial_coverage | `[MitochondrialCoverageBin!]` | - |
| mitochondrial_variants | `[MitochondrialVariant!]!` | - |
| non_coding_constraints | `[NonCodingConstraintRegion!]` | - |
| reference_genome | `ReferenceGenomeId!` | - |
| short_tandem_repeats | `[ShortTandemRepeat!]!` | - |
| start | `Int!` | - |
| stop | `Int!` | - |
| structural_variants | `[StructuralVariant!]!` | - |
| variants | `[Variant!]!` | - |

</details>

### <a id="type-browsermetadata"></a>`BrowserMetadata`

**Used by:** `Query.meta`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| clinvar_release_date | `String!` | - |

</details>

## Statistical & Analysis Types

### <a id="type-variantcooccurrence"></a>`VariantCooccurrence`

**Used by:** `Query.variant_cooccurrence`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| genotype_counts | `[Int!]!` | - |
| haplotype_counts | `[Float!]!` | - |
| populations | `[VariantCooccurrenceInPopulation!]!` | - |
| variant_ids | `[String!]!` | - |
| p_compound_heterozygous | `Float` | - |

</details>

### <a id="type-variantcooccurrenceinpopulation"></a>`VariantCooccurrenceInPopulation`

**Used by:** `VariantCooccurrence.populations`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| genotype_counts | `[Int!]!` | - |
| haplotype_counts | `[Float!]!` | - |
| id | `String!` | - |
| p_compound_heterozygous | `Float` | - |

</details>

### <a id="type-heterozygousvariantcooccurrencecounts"></a>`HeterozygousVariantCooccurrenceCounts`

**Used by:** `Gene.heterozygous_variant_cooccurrence_counts`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| af_cutoff | `String!` | - |
| csq | `String!` | - |
| data | `HeterozygousVariantCooccurrenceCountsData!` | - |

</details>

### <a id="type-homozygousvariantcooccurrencecounts"></a>`HomozygousVariantCooccurrenceCounts`

**Used by:** `Gene.homozygous_variant_cooccurrence_counts`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| af_cutoff | `String!` | - |
| csq | `String!` | - |
| data | `HomozygousVariantCooccurrenceCountsData!` | - |

</details>

### <a id="type-contingencytabletest"></a>`ContingencyTableTest`

**Used by:** `VariantJointFrequencyComparisonStats.contingency_table_test`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| odds_ratio | `String` | - |
| p_value | `Float` | - |

</details>

### <a id="type-cochranmantelhaenszeltest"></a>`CochranMantelHaenszelTest`

**Used by:** `VariantJointFrequencyComparisonStats.cochran_mantel_haenszel_test`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| chisq | `Float` | - |
| p_value | `Float` | - |

</details>

## Variant Alliance Types

### <a id="type-vaallele"></a>`VAAllele`

**Used by:** `VACohortAlleleFrequencyData.focusAllele`, `Variant.vrs`, `VariantDetails.vrs`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| location | `VASequenceLocation!` | - |
| state | `VALiteralSequenceExpression!` | - |
| type | `String!` | - |
| _id | `String` | - |

</details>

### <a id="type-vacohort"></a>`VACohort`

**Used by:** `VACohortAlleleFrequencyData.cohort`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| characteristics | `[VACohortCharacteristic!]` | - |
| id | `String!` | - |
| label | `String` | - |

</details>

### <a id="type-vacohortallelefrequency"></a>`VACohortAlleleFrequency`

A measure of the frequency of an Allele in a cohort.

**Used by:** `Variant.va`, `VariantDetails.va`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| exome | `[VACohortAlleleFrequencyData!]` | - |
| genome | `[VACohortAlleleFrequencyData!]` | - |

</details>

### <a id="type-vasequencelocation"></a>`VASequenceLocation`

**Used by:** `VAAllele.location`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| interval | `VASequenceInterval!` | - |
| sequence_id | `String!` | - |
| type | `String!` | - |
| _id | `String` | - |

</details>

### <a id="type-vaqualitymeasures"></a>`VAQualityMeasures`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| qcFilters | `[String!]` | - |
| fractionCoverage20x | `Float` | - |
| heterozygousSkewedAlleleCount | `Int` | - |
| lossOfFunctionWarning | `Boolean` | - |
| lowComplexityRegion | `Boolean` | - |
| lowConfidenceLossOfFunctionError | `Boolean` | - |
| meanDepth | `Float` | - |
| monoallelic | `Boolean` | - |
| noncodingTranscriptError | `Boolean` | - |

</details>

### <a id="type-vaancillaryresults"></a>`VAAncillaryResults`

**Used by:** `VACohortAlleleFrequencyData.ancillaryResults`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| grpMaxFAF95 | `VAGrpMaxFAF95` | - |
| hemizygotes | `Int` | - |
| homozygotes | `Int` | - |
| jointGrpMaxFAF95 | `VAGrpMaxFAF95` | - |

</details>

## Short Tandem Repeats

### <a id="type-shorttandemrepeat"></a>`ShortTandemRepeat`

**Used by:** `Gene.short_tandem_repeats`, `Query.short_tandem_repeats`, `Region.short_tandem_repeats`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| associated_diseases | `[ShortTandemRepeatAssociatedDisease!]!` | - |
| gene | `ShortTandemRepeatGene!` | - |
| id | `String!` | - |
| main_reference_region | `ShortTandemRepeatReferenceRegion!` | - |
| reference_regions | `[ShortTandemRepeatReferenceRegion!]!` | - |
| reference_repeat_unit | `String!` | - |
| strchive_id | `String` | - |
| stripy_id | `String` | - |

</details>

### <a id="type-shorttandemrepeatdetails"></a>`ShortTandemRepeatDetails`

**Used by:** `Query.short_tandem_repeat`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| adjacent_repeats | `[ShortTandemRepeatAdjacentRepeat!]!` | - |
| age_distribution | `[ShortTandemRepeatAgeDistributionBin!]` | - |
| allele_size_distribution | `[ShortTandemRepeatAlleleSizeDistributionCohort!]!` | - |
| associated_diseases | `[ShortTandemRepeatAssociatedDisease!]!` | - |
| gene | `ShortTandemRepeatGene!` | - |
| genotype_distribution | `[ShortTandemRepeatGenotypeDistributionCohort!]!` | - |
| id | `String!` | - |
| main_reference_region | `ShortTandemRepeatReferenceRegion!` | - |
| reference_regions | `[ShortTandemRepeatReferenceRegion!]!` | - |
| reference_repeat_unit | `String!` | - |
| repeat_units | `[ShortTandemRepeatRepeatUnit!]!` | - |
| strchive_id | `String` | - |
| stripy_id | `String` | - |

</details>

### <a id="type-shorttandemrepeatgene"></a>`ShortTandemRepeatGene`

**Used by:** `ShortTandemRepeat.gene`, `ShortTandemRepeatDetails.gene`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| ensembl_id | `String!` | - |
| region | `String!` | - |
| symbol | `String!` | - |

</details>

### <a id="type-shorttandemrepeatassociateddisease"></a>`ShortTandemRepeatAssociatedDisease`

**Used by:** `ShortTandemRepeat.associated_diseases`, `ShortTandemRepeatDetails.associated_diseases`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| inheritance_mode | `String!` | - |
| name | `String!` | - |
| repeat_size_classifications | `[ShortTandemRepeatAssociatedDiseaseRepeatSizeClassification!]!` | - |
| symbol | `String!` | - |
| notes | `String` | - |
| omim_id | `String` | - |

</details>

### <a id="type-shorttandemrepeatreferenceregion"></a>`ShortTandemRepeatReferenceRegion`

**Used by:** `ShortTandemRepeatAdjacentRepeat.reference_region`, `ShortTandemRepeat.main_reference_region`, `ShortTandemRepeat.reference_regions`
 and 2 more...

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| chrom | `String!` | - |
| reference_genome | `ReferenceGenomeId!` | - |
| start | `Int!` | - |
| stop | `Int!` | - |

</details>

## Histogram & Distribution Types

### <a id="type-histogram"></a>`Histogram`

**Used by:** `MitochondrialVariantAgeDistribution.het`, `MitochondrialVariantAgeDistribution.hom`, `MitochondrialVariantPopulation.heteroplasmy_distribution`
 and 15 more...

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| bin_edges | `[Float!]!` | - |
| bin_freq | `[Float!]!` | - |
| n_larger | `Int` | - |
| n_smaller | `Int` | - |

</details>

### <a id="type-variantagedistribution"></a>`VariantAgeDistribution`

**Used by:** `VariantDetailsSequencingTypeData.age_distribution`, `VariantDetailsJointSequencingTypeData.age_distribution`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| het | `Histogram` | - |
| hom | `Histogram` | - |

</details>

### <a id="type-mitochondrialvariantagedistribution"></a>`MitochondrialVariantAgeDistribution`

**Used by:** `MitochondrialVariantDetails.age_distribution`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| het | `Histogram` | - |
| hom | `Histogram` | - |

</details>

### <a id="type-structuralvariantagedistribution"></a>`StructuralVariantAgeDistribution`

**Used by:** `StructuralVariantDetails.age_distribution`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| het | `Histogram` | - |
| hom | `Histogram` | - |

</details>

## Other Types

These types are used internally or in specific contexts:

### <a id="type-clinvarvariantgnomadsequencingtypedata"></a>`ClinVarVariantGnomadSequencingTypeData`

**Used by:** `ClinVarVariantGnomadData.exome`, `ClinVarVariantGnomadData.genome`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| **ac** | `Int!` | - |
| **an** | `Int!` | - |
| filters | `[String!]!` | - |

</details>

### <a id="type-exacregionalmissenseconstraintregion"></a>`ExacRegionalMissenseConstraintRegion`

**Used by:** `Gene.exac_regional_missense_constraint_regions`, `TranscriptGene.exac_regional_missense_constraint_regions`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| start | `Int!` | - |
| stop | `Int!` | - |
| chisq_diff_null | `Float` | - |
| exp_mis | `Float` | - |
| obs_exp | `Float` | - |
| obs_mis | `Int` | - |

</details>

### <a id="type-heterozygousvariantcooccurrencecountsdata"></a>`HeterozygousVariantCooccurrenceCountsData`

**Used by:** `HeterozygousVariantCooccurrenceCounts.data`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| in_cis | `Int!` | - |
| in_trans | `Int!` | - |
| two_het_total | `Int!` | - |
| unphased | `Int!` | - |

</details>

### <a id="type-homozygousvariantcooccurrencecountsdata"></a>`HomozygousVariantCooccurrenceCountsData`

**Used by:** `HomozygousVariantCooccurrenceCounts.data`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| hom_total | `Int!` | - |

</details>

### <a id="type-mitochondrialvariantgenotypequalityfilter"></a>`MitochondrialVariantGenotypeQualityFilter`

**Used by:** `MitochondrialVariantDetails.genotype_quality_filters`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| name | `String!` | - |
| filtered | `Histogram` | - |

</details>

### <a id="type-mitochondrialvarianthaplogroup"></a>`MitochondrialVariantHaplogroup`

**Used by:** `MitochondrialVariantDetails.haplogroups`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| ac_het | `Int` | - |
| ac_hom | `Int` | - |
| **an** | `Float` | - |
| faf | `Float` | - |
| faf_hom | `Float` | - |
| id | `String` | - |

</details>

### <a id="type-multinucleotidevariantconstituentsnv"></a>`MultiNucleotideVariantConstituentSNV`

**Used by:** `MultiNucleotideVariantDetails.constituent_snvs`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| **variant_id** | `String!` | - |
| exome | `MultiNucleotideVariantConstituentSNVSequencingData` | - |
| genome | `MultiNucleotideVariantConstituentSNVSequencingData` | - |

</details>

### <a id="type-multinucleotidevariantconstituentsnvconsequence"></a>`MultiNucleotideVariantConstituentSNVConsequence`

**Used by:** `MultiNucleotideVariantConsequence.snv_consequences`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| amino_acids | `String!` | - |
| codons | `String!` | - |
| consequence | `String!` | - |
| **variant_id** | `String!` | - |

</details>

### <a id="type-multinucleotidevariantconstituentsnvsequencingdata"></a>`MultiNucleotideVariantConstituentSNVSequencingData`

**Used by:** `MultiNucleotideVariantConstituentSNV.exome`, `MultiNucleotideVariantConstituentSNV.genome`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| filters | `[String!]` | - |
| **ac** | `Int` | - |
| **an** | `Int` | - |

</details>

### <a id="type-multinucleotidevariantdetailssequencingdata"></a>`MultiNucleotideVariantDetailsSequencingData`

**Used by:** `MultiNucleotideVariantDetails.exome`, `MultiNucleotideVariantDetails.genome`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| **ac** | `Int` | - |
| ac_hom | `Int` | - |
| n_individuals | `Int` | - |

</details>

### <a id="type-multinucleotidevariantsummary"></a>`MultiNucleotideVariantSummary`

**Used by:** `MultiNucleotideVariantDetails.related_mnvs`, `VariantDetails.multi_nucleotide_variants`, `VariantDetails.multiNucleotideVariants`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| changes_amino_acids | `Boolean!` | - |
| combined_variant_id | `String!` | - |
| n_individuals | `Int!` | - |
| other_constituent_snvs | `[String!]!` | - |

</details>

### <a id="type-proteinmitochondrialgeneconstraint"></a>`ProteinMitochondrialGeneConstraint`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| exp_lof | `Float!` | - |
| exp_mis | `Float!` | - |
| exp_syn | `Float!` | - |
| obs_lof | `Float!` | - |
| obs_mis | `Float!` | - |
| obs_syn | `Float!` | - |
| oe_lof | `Float!` | - |
| oe_lof_lower | `Float!` | - |
| oe_lof_upper | `Float!` | - |
| oe_mis | `Float!` | - |
| oe_mis_lower | `Float!` | - |
| oe_mis_upper | `Float!` | - |
| oe_syn | `Float!` | - |
| oe_syn_lower | `Float!` | - |
| oe_syn_upper | `Float!` | - |

</details>

### <a id="type-query"></a>`Query`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| gene_search | `[GeneSearchResult!]!` | - |
| liftover | `[LiftoverResult!]!` | - |
| meta | `BrowserMetadata!` | - |
| region | `Region!` | - |
| short_tandem_repeats | `[ShortTandemRepeat!]!` | - |
| variant_search | `[VariantSearchResult!]!` | - |
| clinvar_variant | `ClinVarVariantDetails` | - |
| copy_number_variant | `CopyNumberVariantDetails` | - |
| gene | `Gene` | - |
| mitochondrial_variant | `MitochondrialVariantDetails` | - |
| multiNucleotideVariant | `MultiNucleotideVariantDetails` | - |
| short_tandem_repeat | `ShortTandemRepeatDetails` | - |
| structural_variant | `StructuralVariantDetails` | - |
| transcript | `Transcript` | - |
| variant | `VariantDetails` | - |
| variant_cooccurrence | `VariantCooccurrence` | - |

</details>

### <a id="type-rnamitochondrialgeneconstraint"></a>`RNAMitochondrialGeneConstraint`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| expected | `Float!` | - |
| observed | `Float!` | - |
| oe | `Float!` | - |
| oe_lower | `Float!` | - |
| oe_upper | `Float!` | - |

</details>

### <a id="type-shorttandemrepeatadjacentrepeat"></a>`ShortTandemRepeatAdjacentRepeat`

**Used by:** `ShortTandemRepeatDetails.adjacent_repeats`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| age_distribution | `[ShortTandemRepeatAgeDistributionBin!]` | - |
| allele_size_distribution | `[ShortTandemRepeatAlleleSizeDistributionCohort!]!` | - |
| genotype_distribution | `[ShortTandemRepeatGenotypeDistributionCohort!]!` | - |
| id | `String!` | - |
| reference_region | `ShortTandemRepeatReferenceRegion!` | - |
| reference_repeat_unit | `String!` | - |
| repeat_units | `[String!]!` | - |

</details>

### <a id="type-shorttandemrepeatagedistributionbin"></a>`ShortTandemRepeatAgeDistributionBin`

**Used by:** `ShortTandemRepeatAdjacentRepeat.age_distribution`, `ShortTandemRepeatDetails.age_distribution`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| age_range | `[Int]!` | - |
| distribution | `[[Int!]!]!` | - |

</details>

### <a id="type-shorttandemrepeatallelesizedistributioncohort"></a>`ShortTandemRepeatAlleleSizeDistributionCohort`

**Used by:** `ShortTandemRepeatAdjacentRepeat.allele_size_distribution`, `ShortTandemRepeatDetails.allele_size_distribution`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| ancestry_group | `String!` | - |
| distribution | `[ShortTandemRepeatAlleleSizeItem!]!` | - |
| q_score | `Float!` | - |
| quality_description | `String!` | - |
| repunit | `String!` | - |
| sex | `String!` | - |

</details>

### <a id="type-shorttandemrepeatallelesizeitem"></a>`ShortTandemRepeatAlleleSizeItem`

**Used by:** `ShortTandemRepeatAlleleSizeDistributionCohort.distribution`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| frequency | `Int!` | - |
| repunit_count | `Int!` | - |

</details>

### <a id="type-shorttandemrepeatassociateddiseaserepeatsizeclassification"></a>`ShortTandemRepeatAssociatedDiseaseRepeatSizeClassification`

**Used by:** `ShortTandemRepeatAssociatedDisease.repeat_size_classifications`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| classification | `String!` | - |
| max | `Int` | - |
| min | `Int` | - |

</details>

### <a id="type-shorttandemrepeatgenotypedistributioncohort"></a>`ShortTandemRepeatGenotypeDistributionCohort`

**Used by:** `ShortTandemRepeatAdjacentRepeat.genotype_distribution`, `ShortTandemRepeatDetails.genotype_distribution`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| ancestry_group | `String!` | - |
| distribution | `[ShortTandemRepeatGenotypeItem!]!` | - |
| long_allele_repunit | `String!` | - |
| q_score | `Float!` | - |
| quality_description | `String!` | - |
| sex | `String!` | - |
| short_allele_repunit | `String!` | - |

</details>

### <a id="type-shorttandemrepeatgenotypeitem"></a>`ShortTandemRepeatGenotypeItem`

**Used by:** `ShortTandemRepeatGenotypeDistributionCohort.distribution`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| frequency | `Int!` | - |
| long_allele_repunit_count | `Int!` | - |
| short_allele_repunit_count | `Int!` | - |

</details>

### <a id="type-shorttandemrepeatrepeatunit"></a>`ShortTandemRepeatRepeatUnit`

**Used by:** `ShortTandemRepeatDetails.repeat_units`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| classification | `String!` | - |
| repeat_unit | `String!` | - |

</details>

### <a id="type-statunion"></a>`StatUnion`

**Used by:** `VariantJointFrequencyComparisonStats.stat_union`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| gen_ancs | `[String]` | - |
| p_value | `Float` | - |
| stat_test_name | `String` | - |

</details>

### <a id="type-structuralvariantcopynumber"></a>`StructuralVariantCopyNumber`

**Used by:** `StructuralVariantDetails.copy_numbers`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| **ac** | `Int!` | - |
| copy_number | `Int!` | - |

</details>

### <a id="type-structuralvariantgenotypequality"></a>`StructuralVariantGenotypeQuality`

**Used by:** `StructuralVariantDetails.genotype_quality`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| all | `Histogram` | - |
| alt | `Histogram` | - |

</details>

### <a id="type-vacohortallelefrequencydata"></a>`VACohortAlleleFrequencyData`

**Used by:** `VACohortAlleleFrequencyData.subcohortFrequency`, `VACohortAlleleFrequency.exome`, `VACohortAlleleFrequency.genome`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| alleleFrequency | `Float!` | The frequency of the focusAllele in the cohort. |
| cohort | `VACohort!` | The cohort from which the frequency was derived. |
| focusAllele | `VAAllele!` | The Allele for which the frequency is being reported. |
| focusAlleleCount | `Int!` | The number of occurrences of the focusAllele in the cohort. |
| id | `String!` | - |
| locusAlleleCount | `Int!` | The number of occurrences of alleles at the locus in the cohort (count of all alleles at this locus, sometimes referred to as "allele number"). |
| subcohortFrequency | `[VACohortAlleleFrequencyData!]` | A list of CohortAlleleFrequency objects describing subcohorts of the cohort currently being described. This creates a recursive relationship and subcohorts can be further subdivided into more subcohorts. This enables, for example, the description of different ancestry groups and sexes among those ancestry groups. |
| type | `String!` | - |
| ancillaryResults | `VAAncillaryResults` | Ancillary results that may be associated with the CohortAlleleFrequency, providing additional context or information. |
| derivedFrom | `VACohortAlleleFrequencyDerivation` | Information about the dataset from which the CohortAlleleFrequency was reported. |
| label | `String` | - |

</details>

### <a id="type-vacohortallelefrequencyderivation"></a>`VACohortAlleleFrequencyDerivation`

**Used by:** `VACohortAlleleFrequencyData.derivedFrom`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| id | `String` | The identifier of the dataset. |
| label | `String` | A descriptive label for the dataset. |
| type | `String` | The type of the dataset. (e.g. "DataSet") |
| version | `String` | The version of the dataset. |

</details>

### <a id="type-vacohortcharacteristic"></a>`VACohortCharacteristic`

**Used by:** `VACohort.characteristics`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| name | `String!` | - |
| value | `String!` | - |

</details>

### <a id="type-vacytobandinterval"></a>`VACytobandInterval`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| end | `String!` | - |
| start | `String!` | - |
| type | `String!` | - |

</details>

### <a id="type-vadefiniterange"></a>`VADefiniteRange`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| max | `Float!` | - |
| min | `Float!` | - |
| type | `String!` | - |

</details>

### <a id="type-vaindefiniterange"></a>`VAIndefiniteRange`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| comparator | `VAComparator!` | - |
| type | `String!` | - |
| value | `Float!` | - |

</details>

### <a id="type-valiteralsequenceexpression"></a>`VALiteralSequenceExpression`

**Used by:** `VAAllele.state`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| sequence | `String!` | - |
| type | `String!` | - |

</details>

### <a id="type-vanumber"></a>`VANumber`

**Used by:** `VASequenceInterval.start`, `VASequenceInterval.end`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| type | `String!` | - |
| value | `Int!` | - |

</details>

### <a id="type-vasequenceinterval"></a>`VASequenceInterval`

**Used by:** `VASequenceLocation.interval`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| end | `VANumber!` | - |
| start | `VANumber!` | - |
| type | `String!` | - |

</details>

### <a id="type-variantdetailsjointsequencingtypedata"></a>`VariantDetailsJointSequencingTypeData`

**Used by:** `VariantDetails.joint`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| filters | `[String!]` | - |
| **ac** | `Int` | - |
| age_distribution | `VariantAgeDistribution` | - |
| **an** | `Int` | - |
| faf95 | `VariantFilteringAlleleFrequency` | - |
| faf99 | `VariantFilteringAlleleFrequency` | - |
| freq_comparison_stats | `VariantJointFrequencyComparisonStats` | - |
| hemizygote_count | `Int` | - |
| homozygote_count | `Int` | - |
| populations | `[VariantPopulation]` | - |
| quality_metrics | `VariantQualityMetrics` | - |

</details>

### <a id="type-variantdetailssequencingtypedata"></a>`VariantDetailsSequencingTypeData`

**Used by:** `VariantDetails.exome`, `VariantDetails.genome`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| filters | `[String!]` | - |
| flags | `[String!]` | - |
| **ac** | `Int` | - |
| ac_hemi | `Int` | - |
| ac_hom | `Int` | Deprecated - replaced by homozygote/hemizygote count |
| **af** | `Float` | Deprecated - calculate from AC and AN Preserved for compatibility with existing browser queries |
| age_distribution | `VariantAgeDistribution` | - |
| **an** | `Int` | - |
| faf95 | `VariantFilteringAlleleFrequency` | - |
| faf99 | `VariantFilteringAlleleFrequency` | - |
| hemizygote_count | `Int` | - |
| homozygote_count | `Int` | - |
| local_ancestry_populations | `[VariantLocalAncestryPopulation]` | - |
| populations | `[VariantPopulation]` | - |
| qualityMetrics | `VariantQualityMetrics` | Deprecated - replaced by snake case |
| quality_metrics | `VariantQualityMetrics` | - |

</details>

### <a id="type-variantjointfrequencycomparisonstats"></a>`VariantJointFrequencyComparisonStats`

**Used by:** `VariantDetailsJointSequencingTypeData.freq_comparison_stats`

<details>
<summary><strong>Fields</strong></summary>

| Field | Type | Description |
|-------|------|-------------|
| cochran_mantel_haenszel_test | `CochranMantelHaenszelTest` | - |
| contingency_table_test | `[ContingencyTableTest]` | - |
| stat_union | `StatUnion` | - |

</details>
