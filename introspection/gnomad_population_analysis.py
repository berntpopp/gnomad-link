import requests
import json

GNOMAD_API_URL = "https://gnomad.broadinstitute.org/api"

# Query to explore population structures and example variant data
population_query = """
query PopulationAnalysis {
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
      faf95 {
        popmax
        popmax_population
      }
      populations {
        id
        ac
        an
        homozygote_count
        hemizygote_count
      }
    }
    
    genome {
      ac
      an
      af
      faf95 {
        popmax
        popmax_population
      }
      populations {
        id
        ac
        an
        homozygote_count
        hemizygote_count
      }
    }
    
    joint {
      freq_comparison_stats {
        contingency_table_test {
          p_value
        }
        cochran_mantel_haenszel_test {
          p_value
        }
        stat_union {
          ac_raw
          an_raw
          af_raw
        }
      }
    }
  }
  
  # Get metadata to understand available datasets
  meta {
    datasetIds {
      datasetId
      reference_genome
    }
  }
}
"""

headers = {"Content-Type": "application/json"}
payload = {"query": population_query}

print("=" * 80)
print("gnomAD POPULATION DATA AND QUERY CAPABILITIES ANALYSIS")
print("=" * 80)
print()

try:
    response = requests.post(GNOMAD_API_URL, json=payload, headers=headers)

    if response.status_code != 200:
        print(f"Error: HTTP {response.status_code}")
        print(response.text)
        exit(1)

    data = response.json()

    if "errors" in data:
        print("GraphQL Errors:")
        for error in data["errors"]:
            print(f"  - {error}")
        exit(1)

    # Extract data
    variant_data = data["data"]["variant"]
    meta_data = data["data"]["meta"]

    print("## 1. AVAILABLE DATASETS")
    print("-" * 40)
    for dataset in meta_data["datasetIds"]:
        print(f"\nDataset ID: {dataset['datasetId']}")
        print(f"  Reference genome: {dataset['reference_genome']}")

    print("\n\n## 2. EXAMPLE VARIANT ANALYSIS")
    print("-" * 40)
    print(f"Variant: {variant_data['variant_id']}")
    print(
        f"Position: {variant_data['chrom']}:{variant_data['pos']} {variant_data['ref']}>{variant_data['alt']}"
    )
    if variant_data["rsid"]:
        print(f"rsID: {variant_data['rsid']}")

    # Analyze exome data
    if variant_data["exome"]:
        print("\n### Exome Data:")
        exome = variant_data["exome"]
        print(f"  Total AC/AN: {exome['ac']}/{exome['an']} (AF: {exome['af']:.6f})")
        if exome["faf95"]:
            print(
                f"  FAF95 popmax: {exome['faf95']['popmax']:.6f} ({exome['faf95']['popmax_population']})"
            )

        print("\n  Population Breakdown:")
        for pop in exome["populations"]:
            if pop["ac"] > 0:
                af = pop["ac"] / pop["an"] if pop["an"] > 0 else 0
                print(
                    f"    {pop['id']:20} AC: {pop['ac']:6} AN: {pop['an']:8} AF: {af:.6f} Hom: {pop['homozygote_count']}"
                )

    # Analyze genome data
    if variant_data["genome"]:
        print("\n### Genome Data:")
        genome = variant_data["genome"]
        print(f"  Total AC/AN: {genome['ac']}/{genome['an']} (AF: {genome['af']:.6f})")
        if genome["faf95"]:
            print(
                f"  FAF95 popmax: {genome['faf95']['popmax']:.6f} ({genome['faf95']['popmax_population']})"
            )

        print("\n  Population Breakdown:")
        for pop in genome["populations"]:
            if pop["ac"] > 0:
                af = pop["ac"] / pop["an"] if pop["an"] > 0 else 0
                print(
                    f"    {pop['id']:20} AC: {pop['ac']:6} AN: {pop['an']:8} AF: {af:.6f} Hom: {pop['homozygote_count']}"
                )

    # Analyze joint data
    if variant_data["joint"] and variant_data["joint"]["freq_comparison_stats"]:
        print("\n### Joint Analysis (Exome + Genome):")
        stats = variant_data["joint"]["freq_comparison_stats"]
        if stats["stat_union"]:
            union = stats["stat_union"]
            print(
                f"  Combined AC/AN: {union['ac_raw']}/{union['an_raw']} (AF: {union['af_raw']:.6f})"
            )

        if stats["contingency_table_test"]:
            print(
                f"  Contingency test p-value: {stats['contingency_table_test']['p_value']:.2e}"
            )

    print("\n\n## 3. POPULATION IDENTIFIERS FOUND")
    print("-" * 40)
    all_pops = set()

    if variant_data["exome"] and variant_data["exome"]["populations"]:
        for pop in variant_data["exome"]["populations"]:
            all_pops.add(pop["id"])

    if variant_data["genome"] and variant_data["genome"]["populations"]:
        for pop in variant_data["genome"]["populations"]:
            all_pops.add(pop["id"])

    print("Unique population IDs:")
    for pop_id in sorted(all_pops):
        print(f"  • {pop_id}")

    print("\n\n## 4. KEY FINDINGS FOR GnomAD-MCP IMPLEMENTATION")
    print("-" * 40)
    print(
        """
1. **Population Stratification**
   - Multiple population groups available (e.g., afr, eas, sas, amr, nfe, etc.)
   - Each population has AC, AN, and homozygote counts
   - FAF (Filtering Allele Frequency) available for quality control

2. **Data Types**
   - Separate exome and genome datasets
   - Joint analysis combining both datasets
   - Statistical tests for frequency differences

3. **Frequency Metrics**
   - AC (Allele Count)
   - AN (Allele Number)
   - AF (Allele Frequency)
   - FAF95/FAF99 (Filtering Allele Frequencies)
   - Homozygote and hemizygote counts

4. **Dataset Versions**
   - Multiple gnomAD releases available (r2, r3, r4)
   - Each with different sample sizes and populations
   - Some datasets include non-coding constraint and structural variants
"""
    )

except requests.exceptions.RequestException as e:
    print(f"Network error: {e}")
except json.JSONDecodeError as e:
    print(f"JSON parsing error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
    import traceback

    traceback.print_exc()
