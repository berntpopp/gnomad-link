#!/usr/bin/env python3
"""Test transcript queries against gnomAD API."""

import asyncio
import json

import httpx


async def test_transcript_queries():
    """Test various transcript query formats."""

    url = "https://gnomad.broadinstitute.org/api/"

    # Different query variations to test
    queries = [
        # V4 style query (default)
        {
            "name": "V4 Query (BRCA1)",
            "query": """
            query {
              transcript(
                transcript_id: "ENST00000357654"
                reference_genome: GRCh38
              ) {
                transcript_id
                gene_id
                gene_symbol
                chrom
                start
                stop
              }
            }
            """,
        },
        # V3 style with dataset
        {
            "name": "V3 Query with dataset",
            "query": """
            query {
              transcript(
                transcript_id: "ENST00000357654"
                reference_genome: GRCh38
              ) {
                transcript_id
                gene {
                  gene_id
                  symbol
                }
              }
            }
            """,
        },
        # V2 style with dataset parameter
        {
            "name": "V2 Query attempt",
            "query": """
            query {
              transcript(
                transcript_id: "ENST00000357654"
                reference_genome: GRCh37
              ) {
                transcript_id
                gene_id
              }
            }
            """,
        },
        # Simple query to check field availability
        {
            "name": "Minimal query",
            "query": """
            query {
              transcript(
                transcript_id: "ENST00000357654"
                reference_genome: GRCh38
              ) {
                transcript_id
              }
            }
            """,
        },
        # Check if gene_symbol exists at top level
        {
            "name": "Check gene_symbol field",
            "query": """
            query {
              transcript(
                transcript_id: "ENST00000357654"
                reference_genome: GRCh38
              ) {
                transcript_id
                gene {
                  gene_id
                  symbol
                  gene_version
                  name
                }
                exons {
                  exon_id
                  feature_type
                  start
                  stop
                }
              }
            }
            """,
        },
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        for test in queries:
            print(f"\n=== {test['name']} ===")

            response = await client.post(
                url,
                json={"query": test["query"]},
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                data = response.json()
                if "errors" in data:
                    print("ERRORS:")
                    for error in data["errors"]:
                        print(f"  - {error.get('message', 'Unknown error')}")
                        if "locations" in error:
                            print(f"    at: {error['locations']}")
                elif "data" in data:
                    print("SUCCESS:")
                    print(json.dumps(data["data"], indent=2))
                else:
                    print("No data returned")
            else:
                print(f"HTTP Error: {response.status_code}")
                print(response.text[:500])

    # Now test our current implementation
    print("\n\n=== TESTING OUR SERVER ===")
    await test_our_server()


async def test_our_server():
    """Test our transcript implementation."""

    url = "http://localhost:8000/api/transcript/ENST00000357654"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(url, params={"reference_genome": "GRCh38"})

            if response.status_code == 200:
                data = response.json()
                print("Our server response:")
                print(f"  - transcript_id: {data.get('transcript_id')}")
                print(f"  - gene_symbol: {data.get('gene_symbol')}")
                print(f"  - Fields returned: {list(data.keys())}")
            else:
                print(f"Error: {response.status_code}")
                print(response.json())
        except httpx.ConnectError:
            print(
                "Could not connect to local server. Make sure it's running on port 8000."
            )
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_transcript_queries())
