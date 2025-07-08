#!/usr/bin/env python3
"""Debug transcript not found behavior."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gnomad_mcp.api.client import UnifiedGnomadClient


async def debug_transcript_not_found():
    """Debug what happens with non-existent transcript."""

    client = UnifiedGnomadClient()

    try:
        print("Testing non-existent transcript...")
        result = await client.get_transcript("ENST99999999999", "GRCh38")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {e}")

        # Test the actual GraphQL response
        import json

        import httpx

        print("\n\nTesting directly against gnomAD API...")
        query = """
        query {
            transcript(
                transcript_id: "ENST99999999999"
                reference_genome: GRCh38
            ) {
                transcript_id
            }
        }
        """

        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(
                "https://gnomad.broadinstitute.org/api/",
                json={"query": query},
                headers={"Content-Type": "application/json"},
            )

            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Response: {json.dumps(data, indent=2)}")


if __name__ == "__main__":
    asyncio.run(debug_transcript_not_found())
