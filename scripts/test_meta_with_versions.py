#!/usr/bin/env python3
"""Test if meta query needs version-specific parameters."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gql import gql

from gnomad_mcp.api.base_client import BaseGnomadClient


async def test_meta_with_parameters():
    """Test meta query with different parameters."""
    client = BaseGnomadClient()

    # Test 1: Plain meta query
    query_string = """
    query meta {
        meta {
            clinvar_release_date
        }
    }
    """

    print("Test 1: Plain meta query (no parameters)")
    try:
        query_doc = gql(query_string)
        result = await client._client.execute_async(query_doc)
        print(f"✓ Success! ClinVar release date: {result['meta']['clinvar_release_date']}")
    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {e}")

    # Test 2: Meta query with dataset parameter (v2 style)
    query_string_v2 = """
    query meta($dataset: DatasetId!) {
        meta(dataset: $dataset) {
            clinvar_release_date
        }
    }
    """

    print("\nTest 2: Meta query with dataset parameter (v2 style)")
    try:
        query_doc = gql(query_string_v2)
        result = await client._client.execute_async(
            query_doc, variable_values={"dataset": "gnomad_r2_1"}
        )
        print(f"✓ Success with dataset! Result: {result}")
    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {e}")

    # Test 3: Meta query with reference_genome parameter
    query_string_v3 = """
    query meta($reference_genome: ReferenceGenomeId!) {
        meta(reference_genome: $reference_genome) {
            clinvar_release_date
        }
    }
    """

    print("\nTest 3: Meta query with reference_genome parameter")
    try:
        query_doc = gql(query_string_v3)
        result = await client._client.execute_async(
            query_doc, variable_values={"reference_genome": "GRCh38"}
        )
        print(f"✓ Success with reference_genome! Result: {result}")
    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {e}")

    # Test 4: Check what other fields are available in meta
    query_introspect = """
    query IntrospectMeta {
        __type(name: "MetaData") {
            name
            fields {
                name
                type {
                    name
                    kind
                }
            }
        }
    }
    """

    print("\nTest 4: Introspecting MetaData type")
    try:
        query_doc = gql(query_introspect)
        result = await client._client.execute_async(query_doc)
        if result['__type'] and result['__type']['fields']:
            print("Available fields in MetaData:")
            for field in result['__type']['fields']:
                print(f"  - {field['name']}: {field['type']['name']}")
    except Exception as e:
        print(f"✗ Error introspecting: {type(e).__name__}: {e}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(test_meta_with_parameters())
