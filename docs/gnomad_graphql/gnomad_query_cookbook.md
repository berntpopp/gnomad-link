# gnomAD Query Cookbook

## 🍳 Ready-to-Use Query Recipes

### Population Genetics Queries

#### Get Variant with All Population Frequencies
```graphql
query GetVariantPopulations($variantId: String!, $dataset: DatasetId!) {
  variant(variantId: $variantId, dataset: $dataset) {
    variant_id
    reference_genome
    
    # Overall frequencies
    genome {
      af
      ac
      an
      ac_hom
      ac_hemi
      
      # Population breakdown
      populations {
        id
        af
        ac
        an
        ac_hom
        ac_hemi
      }
    }
    
    # Exome frequencies (if available)
    exome {
      af
      populations {
        id
        af
      }
    }
  }
}
```

#### Find Rare Variants in a Gene
```graphql
query FindRareVariants($gene: String!, $dataset: DatasetId!) {
  variant_search(query: $gene, dataset: $dataset) {
    variant_id
    af
    consequence
    hgvsp
  }
}

# Then filter client-side for af < 0.001
```

### Clinical Genetics Queries

#### Get Complete Clinical Information
```graphql
query GetClinicalData($variantId: String!, $dataset: DatasetId!, $referenceGenome: ReferenceGenomeId!) {
  # gnomAD data
  variant(variantId: $variantId, dataset: $dataset) {
    variant_id
    rsid
    genome { af }
    
    transcript_consequences {
      gene_symbol
      consequence
      hgvsc
      hgvsp
      polyphen_prediction
      sift_prediction
      lof
      lof_filter
    }
  }
  
  # ClinVar data
  clinvar_variant(variant_id: $variantId, reference_genome: $referenceGenome) {
    clinical_significance
    review_status
    last_evaluated
    
    conditions {
      name
      medgen_id
      omim_id
    }
    
    submissions {
      clinical_significance
      review_status
      submitter_name
      conditions {
        name
      }
    }
  }
}
```

#### Get Gene Constraint for Disease Gene List
```graphql
query GetConstraintScores($genes: [String!]!, $referenceGenome: ReferenceGenomeId!) {
  gene1: gene(gene_symbol: $genes[0], reference_genome: $referenceGenome) {
    ...GeneConstraint
  }
  gene2: gene(gene_symbol: $genes[1], reference_genome: $referenceGenome) {
    ...GeneConstraint
  }
  # Repeat for each gene...
}

fragment GeneConstraint on Gene {
  symbol
  gnomad_constraint {
    pLI
    oe_lof
    oe_lof_lower
    oe_lof_upper
    oe_mis
    oe_mis_lower
    oe_mis_upper
  }
}
```

### Structural Variant Queries

#### Get Structural Variants in a Region
```graphql
query GetSVsInRegion($chrom: String!, $start: Int!, $stop: Int!, $dataset: StructuralVariantDatasetId!) {
  region(chrom: $chrom, start: $start, stop: $stop) {
    structural_variants(dataset: $dataset) {
      variant_id
      chrom
      pos
      end
      length
      type
      populations {
        id
        af
      }
    }
  }
}
```

### Research Queries

#### Compare Frequencies Across Datasets
```graphql
query CompareDatasets($variantId: String!) {
  v4: variant(variantId: $variantId, dataset: gnomad_r4) {
    genome { af }
  }
  
  v3: variant(variantId: $variantId, dataset: gnomad_r3) {
    genome { af }
  }
  
  v2: variant(variantId: $variantId, dataset: gnomad_r2_1) {
    genome { af }
  }
}
```

#### Get Mitochondrial Variant with Haplogroups
```graphql
query GetMitoVariant($variantId: String!, $dataset: DatasetId!) {
  mitochondrial_variant(variant_id: $variantId, dataset: $dataset) {
    variant_id
    
    # Overall frequencies
    ac_hom
    ac_het
    an
    af_hom
    af_het
    
    # Haplogroup distribution
    haplogroups {
      id
      ac_hom
      ac_het
      an
      af_hom
      af_het
    }
    
    # Population distribution
    populations {
      id
      ac_hom
      ac_het
      an
    }
  }
}
```

### Advanced Patterns

#### Batch Query Multiple Variants
```graphql
query BatchVariants {
  var1: variant(variantId: "1-55516888-G-A", dataset: gnomad_r4) {
    ...VariantInfo
  }
  var2: variant(variantId: "2-234567890-C-T", dataset: gnomad_r4) {
    ...VariantInfo
  }
  var3: variant(variantId: "3-123456789-A-G", dataset: gnomad_r4) {
    ...VariantInfo
  }
}

fragment VariantInfo on VariantDetails {
  variant_id
  genome { af }
  transcript_consequences {
    gene_symbol
    consequence
  }
}
```

#### Get Variant with Coverage Information
```graphql
query GetVariantWithCoverage($variantId: String!, $dataset: DatasetId!) {
  variant(variantId: $variantId, dataset: $dataset) {
    variant_id
    genome { af }
    
    # Coverage at this position
    coverage {
      genome {
        mean
        median
        over_20
      }
    }
  }
}
```

### Utility Queries

#### Get All Available Datasets
```graphql
query GetDatasets {
  meta {
    datasets {
      gnomad_r4 {
        label
        reference_genome
        sample_count
      }
      gnomad_r3 {
        label
        reference_genome
        sample_count
      }
      gnomad_r2_1 {
        label
        reference_genome
        sample_count
      }
    }
  }
}
```

#### Check Variant Co-occurrence
```graphql
query CheckCooccurrence($variant1: String!, $variant2: String!, $dataset: DatasetId!) {
  variant_cooccurrence(
    variants: [$variant1, $variant2]
    dataset: $dataset
  ) {
    variant_ids
    genotype_counts {
      genotype
      count
    }
  }
}
```

## 📝 Query Tips

1. **Use Fragments** for repeated structures
2. **Alias Fields** when querying multiple items
3. **Request Only Needed Fields** to improve performance
4. **Handle Null Results** - not all variants exist in all datasets
5. **Check Rate Limits** - implement appropriate delays

## 🔗 Related Documentation

- [API Reference](gnomad_graphql_api_reference.md)
- [Type Reference](gnomad_type_reference.md)
- [Quick Start Guide](gnomad_quick_start.md)
