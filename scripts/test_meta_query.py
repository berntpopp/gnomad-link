#!/usr/bin/env python3
"""Test meta query across different gnomAD versions."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gql import gql

from gnomad_mcp.api.base_client import BaseGnomadClient


async def test_meta_query():
    """Test meta query for different versions."""
    client = BaseGnomadClient()

    # Query for meta information
    query_string = """
    query meta {
        meta {
            clinvar_release_date
        }
    }
    """

    print("Testing meta query...")

    try:
        query_doc = gql(query_string)
        result = await client._client.execute_async(query_doc)
        print(f"Success! Result: {result}")

        if "meta" in result:
            meta_data = result["meta"]
            print(f"ClinVar release date: {meta_data.get('clinvar_release_date', 'Not found')}")

    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(test_meta_query())
