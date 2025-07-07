"""Example queries demonstrating gnomAD API capabilities."""

import json

import requests

GNOMAD_API_URL = "https://gnomad.broadinstitute.org/api"

# Example queries demonstrating gnomAD API capabilities

queries = {
    "1. Simple Variant Query": """
query SimpleVariant {
  variant(variantId: "1-55039447-G-T", dataset: gnomad_r4) {
    variant_id
    reference_genome
    chrom
    pos
    ref
    alt
    rsid

    exome {
      ac
      an
      af
      filters
    }

    genome {
      ac
      an
      af
      filters
    }
  }
}
""",
    "2. Variant with Population Data": """
query VariantWithPopulations {
  variant(variantId: "1-55516888-G-A", dataset: gnomad_r4) {
    variant_id

    exome {
      ac
      an
      af
      populations {
        id
        ac
        an
        homozygote_count
      }
    }
  }
}
""",
    "3. Gene Query": """
query GeneInfo {
  gene(gene_symbol: "PCSK9", reference_genome: GRCh38) {
    gene_id
    gene_symbol
    chrom
    start
    stop

    canonical_transcript_id
    omim_id

    mane_select_transcript {
      ensembl_id
      refseq_id
    }
  }
}
""",
    "4. Region Query": """
query RegionVariants {
  region(chrom: "1", start: 55039400, stop: 55039500, reference_genome: GRCh38) {
    variants(dataset: gnomad_r4) {
      variant_id
      pos
      ref
      alt

      exome {
        ac
        an
        af
      }
    }
  }
}
""",
    "5. ClinVar Variant": """
query ClinVarVariant {
  clinvar_variant(variant_id: "1-55039447-G-T", reference_genome: GRCh38) {
    variant_id
    review_status
    clinical_significance

    gnomad {
      exome {
        ac
        an
        af
      }
    }
  }
}
""",
}

print("=" * 80)
print("gnomAD API EXAMPLE QUERIES AND RESPONSES")
print("=" * 80)
print()

headers = {"Content-Type": "application/json"}

for query_name, query in queries.items():
    print(f"\n## {query_name}")
    print("-" * 40)
    print("Query:")
    print(query.strip())
    print("\nResponse:")

    payload = {"query": query}

    try:
        response = requests.post(GNOMAD_API_URL, json=payload, headers=headers)

        if response.status_code != 200:
            print(f"Error: HTTP {response.status_code}")
            continue

        data = response.json()

        if "errors" in data:
            print("GraphQL Errors:")
            for error in data["errors"]:
                print(f"  - {error['message']}")
        else:
            print(json.dumps(data["data"], indent=2))

    except Exception as e:
        print(f"Error: {e}")

    print()

print("\n" + "=" * 80)
print("SUMMARY: KEY API CAPABILITIES FOR GnomAD-MCP")
print("=" * 80)
print(
    """
Based on the example queries above, the gnomAD API provides:

1. **Variant Queries**
   - Single variant lookup by ID
   - Population-specific allele frequencies
   - Separate exome and genome data
   - Quality filters and flags

2. **Gene Queries**
   - Gene information and boundaries
   - Canonical transcript identification
   - MANE select transcript data

3. **Region Queries**
   - Retrieve all variants in a genomic region
   - Batch variant data retrieval

4. **ClinVar Integration**
   - Clinical significance data
   - Cross-reference with population frequencies

5. **Data Structure**
   - Hierarchical organization (variant -> exome/genome -> populations)
   - Consistent field naming across queries
   - Support for multiple reference genomes (GRCh37/GRCh38)
   - Multiple dataset versions (gnomad_r2, gnomad_r3, gnomad_r4)

6. **Population Stratification**
   - Detailed population breakdowns
   - Homozygote counts
   - Filtering allele frequencies (FAF)

This API structure is ideal for implementing an MCP server that provides:
- Variant frequency lookups
- Population-specific analysis
- Clinical variant interpretation
- Regional variant discovery
"""
)
