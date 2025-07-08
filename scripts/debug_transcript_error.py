#!/usr/bin/env python3
"""Debug transcript query error."""

import asyncio
import sys
import traceback
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gnomad_mcp.api.client import UnifiedGnomadClient


async def debug_transcript():
    """Debug transcript query directly."""

    client = UnifiedGnomadClient()

    try:
        print("Testing transcript query...")
        result = await client.get_transcript("ENST00000357654", "GRCh38")
        print("Success!")
        print(f"Keys in result: {list(result.keys())}")
        if "transcript" in result:
            print(f"Transcript ID: {result['transcript']['transcript_id']}")
        else:
            print(f"Full result: {result}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        traceback.print_exc()

        # Try to debug query loading
        print("\n\nDebugging query loading...")
        try:
            query_string = client.query_loader.load_query("transcript", "v4")
            print("Query loaded successfully")
            print(f"Query length: {len(query_string)} characters")
            print("First 200 chars:")
            print(query_string[:200])
        except Exception as qe:
            print(f"Query loading error: {qe}")


if __name__ == "__main__":
    asyncio.run(debug_transcript())
