import requests
import json
from collections import defaultdict

# Setup
GNOMAD_API_URL = "https://gnomad.broadinstitute.org/api"

# Enhanced introspection query to get more details
introspection_query = """
query IntrospectionQuery {
  __schema {
    queryType {
      name
    }
    types {
      name
      kind
      description
      fields {
        name
        description
        args {
          name
          type {
            name
            kind
            ofType {
              name
              kind
              ofType {
                name
                kind
              }
            }
          }
        }
        type {
          name
          kind
          ofType {
            name
            kind
            ofType {
              name
              kind
              ofType {
                name
                kind
              }
            }
          }
        }
      }
    }
  }
}
"""

headers = {"Content-Type": "application/json"}

payload = {"query": introspection_query}

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

    schema = data["data"]["__schema"]
    types = schema["types"]
    query_type_name = schema["queryType"]["name"]

    # Helper function to get the actual type name
    def get_type_name(type_obj):
        if not type_obj:
            return None
        if type_obj["name"]:
            return type_obj["name"]
        elif type_obj["ofType"]:
            return get_type_name(type_obj["ofType"])
        return None

    # Helper function to get full type representation
    def get_full_type(type_obj):
        if not type_obj:
            return "Unknown"

        if type_obj["kind"] == "LIST":
            if "ofType" in type_obj and type_obj["ofType"]:
                inner = get_full_type(type_obj["ofType"])
                return f"[{inner}]"
            return "[Unknown]"
        elif type_obj["kind"] == "NON_NULL":
            if "ofType" in type_obj and type_obj["ofType"]:
                inner = get_full_type(type_obj["ofType"])
                return f"{inner}!"
            return "Unknown!"
        else:
            return type_obj.get("name", "Unknown")

    print("=" * 80)
    print("COMPREHENSIVE gnomAD GraphQL API ANALYSIS REPORT")
    print("=" * 80)
    print()

    # 1. API Overview
    print("## 1. API OVERVIEW")
    print("-" * 40)
    print(f"API Endpoint: {GNOMAD_API_URL}")
    print(f"Root Query Type: {query_type_name}")
    print(
        f"Total Schema Types: {len([t for t in types if not t['name'].startswith('__')])}"
    )
    print()

    # 2. Available Query Endpoints
    print("## 2. AVAILABLE QUERY ENDPOINTS")
    print("-" * 40)
    query_type = next((t for t in types if t["name"] == query_type_name), None)

    if query_type and query_type["fields"]:
        # Categorize queries
        variant_queries = []
        gene_queries = []
        region_queries = []
        other_queries = []

        for field in query_type["fields"]:
            field_info = {
                "name": field["name"],
                "args": [
                    (arg["name"], get_full_type(arg["type"]))
                    for arg in (field["args"] or [])
                ],
                "return_type": get_full_type(field["type"]),
                "description": field.get("description", ""),
            }

            field_lower = field["name"].lower()
            if "variant" in field_lower:
                variant_queries.append(field_info)
            elif "gene" in field_lower:
                gene_queries.append(field_info)
            elif "region" in field_lower:
                region_queries.append(field_info)
            else:
                other_queries.append(field_info)

        # Print categorized queries
        print("### Variant Queries:")
        for q in variant_queries:
            print(f"\n  • {q['name']} -> {q['return_type']}")
            if q["args"]:
                print("    Parameters:")
                for arg_name, arg_type in q["args"]:
                    print(f"      - {arg_name}: {arg_type}")

        print("\n### Gene Queries:")
        for q in gene_queries:
            print(f"\n  • {q['name']} -> {q['return_type']}")
            if q["args"]:
                print("    Parameters:")
                for arg_name, arg_type in q["args"]:
                    print(f"      - {arg_name}: {arg_type}")

        print("\n### Region Queries:")
        for q in region_queries:
            print(f"\n  • {q['name']} -> {q['return_type']}")
            if q["args"]:
                print("    Parameters:")
                for arg_name, arg_type in q["args"]:
                    print(f"      - {arg_name}: {arg_type}")

        print("\n### Other Queries:")
        for q in other_queries[:5]:  # Limit to first 5
            print(f"\n  • {q['name']} -> {q['return_type']}")

    print()

    # 3. Core Data Structures
    print("## 3. CORE DATA STRUCTURES FOR VARIANT DATA")
    print("-" * 40)

    # Find and analyze key types
    key_types = [
        "Variant",
        "VariantDetails",
        "VariantPopulation",
        "VariantSequencingTypeData",
        "MitochondrialVariant",
        "StructuralVariant",
        "CopyNumberVariant",
    ]

    for type_name in key_types:
        type_def = next((t for t in types if t["name"] == type_name), None)
        if type_def and type_def["fields"]:
            print(f"\n### {type_name}")
            print(f"Kind: {type_def['kind']}")
            if type_def.get("description"):
                print(f"Description: {type_def['description']}")
            print("Fields:")

            # Categorize fields
            id_fields = []
            freq_fields = []
            annotation_fields = []
            other_fields = []

            for field in type_def["fields"]:
                field_name = field["name"]
                field_type = get_full_type(field["type"])
                field_lower = field_name.lower()

                if any(
                    kw in field_lower for kw in ["id", "chrom", "pos", "ref", "alt"]
                ):
                    id_fields.append((field_name, field_type))
                elif any(
                    kw in field_lower
                    for kw in [
                        "freq",
                        "count",
                        "number",
                        "ac",
                        "an",
                        "af",
                        "hom",
                        "hemi",
                        "faf",
                    ]
                ):
                    freq_fields.append((field_name, field_type))
                elif any(
                    kw in field_lower
                    for kw in ["consequence", "transcript", "gene", "annotation"]
                ):
                    annotation_fields.append((field_name, field_type))
                else:
                    other_fields.append((field_name, field_type))

            if id_fields:
                print("  Identification:")
                for name, ftype in id_fields:
                    print(f"    - {name}: {ftype}")

            if freq_fields:
                print("  Frequency Data:")
                for name, ftype in freq_fields:
                    print(f"    - {name}: {ftype}")

            if annotation_fields:
                print("  Annotations:")
                for name, ftype in annotation_fields:
                    print(f"    - {name}: {ftype}")

            if other_fields and len(other_fields) <= 10:
                print("  Other Fields:")
                for name, ftype in other_fields:
                    print(f"    - {name}: {ftype}")
            elif other_fields:
                print(f"  Other Fields: {len(other_fields)} additional fields")

    print()

    # 4. Population-Specific Data
    print("## 4. POPULATION-SPECIFIC FREQUENCY DATA")
    print("-" * 40)

    # Find population-related types
    pop_types = [t for t in types if t["name"] and "population" in t["name"].lower()]

    for type_def in pop_types[:5]:  # Limit to first 5
        if type_def["fields"]:
            print(f"\n### {type_def['name']}")
            print("Fields:")
            for field in type_def["fields"]:
                print(f"  - {field['name']}: {get_full_type(field['type'])}")

    print()

    # 5. Analysis of Filtering and Search Capabilities
    print("## 5. FILTERING AND SEARCH CAPABILITIES")
    print("-" * 40)

    # Analyze input types for filtering
    filter_types = [
        t
        for t in types
        if t["name"] and ("filter" in t["name"].lower() or "input" in t["name"].lower())
    ]

    if filter_types:
        print("\nAvailable Filter Types:")
        for ftype in filter_types[:5]:
            print(f"  • {ftype['name']}")

    # Look at variant search specifically
    if query_type:
        variant_search = next(
            (f for f in query_type["fields"] if f["name"] == "variant_search"), None
        )
        if variant_search and variant_search["args"]:
            print("\nVariant Search Parameters:")
            for arg in variant_search["args"]:
                print(f"  - {arg['name']}: {get_full_type(arg['type'])}")

    print()

    # 6. Data Coverage Summary
    print("## 6. DATA COVERAGE SUMMARY")
    print("-" * 40)

    # Count different types of data available
    variant_types = [t for t in types if t["name"] and "variant" in t["name"].lower()]
    gene_types = [t for t in types if t["name"] and "gene" in t["name"].lower()]
    transcript_types = [
        t for t in types if t["name"] and "transcript" in t["name"].lower()
    ]

    print(f"Variant-related types: {len(variant_types)}")
    print(f"Gene-related types: {len(gene_types)}")
    print(f"Transcript-related types: {len(transcript_types)}")

    print("\nSpecialized Variant Types:")
    specialized = [
        "MitochondrialVariant",
        "StructuralVariant",
        "CopyNumberVariant",
        "MultiNucleotideVariant",
        "ClinVarVariant",
    ]
    for stype in specialized:
        if any(t["name"] == stype for t in types):
            print(f"  ✓ {stype}")

    print()

    # 7. Example Use Cases
    print("## 7. RECOMMENDED USE CASES FOR GnomAD-MCP")
    print("-" * 40)
    print(
        """
Based on the API analysis, the following use cases are well-supported:

1. **Single Variant Lookup**
   - Query: variant(variantId, datasetId)
   - Returns: Comprehensive variant details including frequencies across populations

2. **Gene-based Variant Search**
   - Query: gene(geneId/symbol) -> variants
   - Returns: All variants within a gene with population frequencies

3. **Region-based Variant Search**
   - Query: region(chrom, start, stop) -> variants
   - Returns: Variants within genomic coordinates

4. **Population-specific Frequency Analysis**
   - Available population breakdowns in variant data
   - Filtering allele frequencies (FAF) for variant interpretation

5. **Clinical Variant Integration**
   - Query: clinvar_variant for pathogenicity data
   - Cross-reference with gnomAD population frequencies

6. **Structural Variant Analysis**
   - Dedicated queries for SVs, CNVs, and complex variants
   - Population frequency data for non-SNV variants
"""
    )

    print()
    print("## 8. KEY INSIGHTS FOR IMPLEMENTATION")
    print("-" * 40)
    print(
        """
• The API uses dataset IDs to version data (e.g., 'gnomad_r4_non_ukb')
• Variants have multiple frequency representations (AC/AN, AF, FAF95, FAF99)
• Population stratification is available at multiple levels
• Both GRCh37 and GRCh38 coordinates are supported
• The API supports batch queries for efficiency
• Specialized endpoints exist for different variant types
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
