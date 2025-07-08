#!/usr/bin/env python3
"""Debug transcript query directly to gnomAD API."""

import asyncio
import json

import httpx


async def test_gnomad_directly():
    """Test transcript query directly against gnomAD API."""

    url = "https://gnomad.broadinstitute.org/api/"

    # Test v4 query with minimal fields first
    minimal_query = """
    query {
        transcript(
            transcript_id: "ENST00000357654"
            reference_genome: GRCh38
        ) {
            transcript_id
            gene_id
        }
    }
    """

    async with httpx.AsyncClient(timeout=30.0) as client:
        print("=== Testing minimal transcript query ===")
        response = await client.post(
            url,
            json={"query": minimal_query},
            headers={"Content-Type": "application/json"},
        )

        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if "errors" in data:
                print("Errors:")
                for error in data["errors"]:
                    print(f"  - {error['message']}")
            else:
                print("Success:")
                print(json.dumps(data, indent=2))
        else:
            print(f"HTTP Error: {response.text[:500]}")

        # Now test with more fields
        print("\n\n=== Testing fuller transcript query ===")
        fuller_query = """
        query {
            transcript(
                transcript_id: "ENST00000357654"
                reference_genome: GRCh38
            ) {
                transcript_id
                transcript_version
                gene_id
                gene {
                    gene_id
                    symbol
                }
                exons {
                    feature_type
                    start
                    stop
                }
            }
        }
        """

        response = await client.post(
            url,
            json={"query": fuller_query},
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 200:
            data = response.json()
            if "data" in data and data["data"]["transcript"]:
                t = data["data"]["transcript"]
                print(f"transcript_id: {t['transcript_id']}")
                print(f"gene.symbol: {t['gene']['symbol'] if t.get('gene') else 'N/A'}")
                print(f"exons count: {len(t.get('exons', []))}")


if __name__ == "__main__":
    asyncio.run(test_gnomad_directly())
