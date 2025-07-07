"""Introspection module for the gnomAD GraphQL API."""

import json

import requests

# Step 1: Setup
GNOMAD_API_URL = "https://gnomad.broadinstitute.org/api"

# Step 2: Create Introspection Query
introspection_query = """
query IntrospectionQuery {
  __schema {
    queryType {
      name
    }
    types {
      name
      kind
      fields {
        name
        type {
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
"""

# Step 3: Execute Query
headers = {"Content-Type": "application/json"}

payload = {"query": introspection_query}

try:
    response = requests.post(GNOMAD_API_URL, json=payload, headers=headers)

    if response.status_code != 200:
        print(f"Error: HTTP {response.status_code}")
        print(response.text)
        exit(1)

    # Step 4: Process Schema
    data = response.json()

    if "errors" in data:
        print("GraphQL Errors:")
        for error in data["errors"]:
            print(f"  - {error}")
        exit(1)

    schema = data["data"]["__schema"]
    types = schema["types"]
    query_type_name = schema["queryType"]["name"]

    # Step 5: Analyze and Report
    print("*** gnomAD API Introspection Report ***")
    print()

    # 1. Root Query Type
    print("### Root Query Information ###")
    print(f"Root Query Type Name: {query_type_name}")
    print()

    # 2. Identify Variant-Related Queries
    print("### Relevant Query Fields ###")
    query_type = next((t for t in types if t["name"] == query_type_name), None)
    if query_type and query_type["fields"]:
        variant_related_queries = []
        for field in query_type["fields"]:
            field_name = field["name"].lower()
            if any(
                keyword in field_name
                for keyword in ["variant", "gene", "region", "transcript"]
            ):
                variant_related_queries.append(field["name"])

        for query in sorted(variant_related_queries):
            print(f"- {query}")
    print()

    # 3. Identify Variant-Related Data Structures
    print("### Core Variant Data Structures ###")
    variant_types = []
    for type_def in types:
        if type_def["name"] and not type_def["name"].startswith("__"):
            type_name_lower = type_def["name"].lower()
            if any(
                keyword in type_name_lower
                for keyword in ["variant", "allele", "frequency", "population"]
            ):
                variant_types.append(type_def["name"])

    for vtype in sorted(set(variant_types)):
        print(f"- {vtype}")
    print()

    # 4. Detail the Variant Type
    print("### Key Fields in 'Variant' Type for Allele Frequency ###")

    # Find the main Variant type
    variant_type = None
    for type_def in types:
        if type_def["name"] == "Variant":
            variant_type = type_def
            break

    if variant_type and variant_type["fields"]:
        frequency_fields = []
        for field in variant_type["fields"]:
            field_name = field["name"].lower()
            # Look for fields related to allele frequency
            if any(
                keyword in field_name
                for keyword in [
                    "allele",
                    "frequency",
                    "freq",
                    "count",
                    "number",
                    "population",
                    "pop",
                    "ac",
                    "an",
                    "af",
                    "hom",
                ]
            ):
                frequency_fields.append(field["name"])

        # Also include important ID fields
        for field in variant_type["fields"]:
            if field["name"] in [
                "variant_id",
                "variantId",
                "id",
                "pos",
                "chrom",
                "ref",
                "alt",
            ]:
                if field["name"] not in frequency_fields:
                    frequency_fields.append(field["name"])

        for field in sorted(frequency_fields):
            print(f"- {field}")
    else:
        print("Note: Could not find a 'Variant' type in the schema.")
        # Try to find alternative variant types
        for type_def in types:
            if (
                type_def["name"]
                and "variant" in type_def["name"].lower()
                and type_def["fields"]
            ):
                print(f"\nAlternative type found: {type_def['name']}")
                for field in type_def["fields"][:10]:  # Show first 10 fields
                    print(f"  - {field['name']}")
                break

except requests.exceptions.RequestException as e:
    print(f"Network error: {e}")
except json.JSONDecodeError as e:
    print(f"JSON parsing error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
