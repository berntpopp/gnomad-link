# gnomAD API Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### 1. Basic Setup

```python
import requests

# API endpoint
url = "https://gnomad.broadinstitute.org/api/"

# Helper function
def query_gnomad(query):
    response = requests.post(url, json={"query": query})
    return response.json()
```

### 2. Your First Query - Get Variant Frequency

```python
# Get allele frequency for a variant
query = '''
{
  variant(variantId: "1-55516888-G-A", dataset: gnomad_r4) {
    variant_id
    genome {
      af
      ac
      an
    }
  }
}
'''

result = query_gnomad(query)
print(f"Allele frequency: {result['data']['variant']['genome']['af']}")
```

### 3. Essential Queries

#### Get Gene Constraint Scores
```graphql
{
  gene(gene_symbol: "BRCA2", reference_genome: GRCh38) {
    symbol
    gnomad_constraint {
      pLI
      oe_lof
      oe_lof_lower
      oe_lof_upper
    }
  }
}
```

#### Search for Variants in a Gene
```graphql
{
  variant_search(query: "APOE", dataset: gnomad_r4) {
    variant_id
    af
    consequence
  }
}
```

#### Get ClinVar Annotations
```graphql
{
  clinvar_variant(variant_id: "7-117559590-ATCT-A", reference_genome: GRCh38) {
    clinical_significance
    review_status
    conditions {
      name
    }
  }
}
```

#### Liftover Coordinates
```graphql
{
  liftover(source_variant_id: "17-7577121-G-A", reference_genome: GRCh37) {
    liftover {
      variant_id
      reference_genome
    }
  }
}
```

### 4. Common Patterns

#### Pattern 1: Get Population-Specific Frequencies
```graphql
{
  variant(variantId: "1-55516888-G-A", dataset: gnomad_r4) {
    genome {
      populations {
        id
        af
      }
    }
  }
}
```

#### Pattern 2: Get Functional Predictions
```graphql
{
  variant(variantId: "1-55516888-G-A", dataset: gnomad_r4) {
    transcript_consequences {
      gene_symbol
      consequence
      polyphen_prediction
      sift_prediction
      lof
    }
  }
}
```

### 5. Tips & Tricks

1. **Variant ID Format**: `chromosome-position-reference-alternate`
   - Example: `1-55516888-G-A`

2. **Choose the Right Dataset**:
   - `gnomad_r4`: Latest, GRCh38
   - `gnomad_r2_1`: Legacy, GRCh37

3. **Request Only What You Need**:
   - Don't request all fields
   - Use specific field selection

4. **Handle Nulls**:
   - Variants may not exist in all datasets
   - Some fields may be null

### 6. Next Steps

- [Full API Reference](gnomad_graphql_api_reference.md)
- [Query Cookbook](gnomad_query_cookbook.md)
- [Type Reference](gnomad_type_reference.md)
