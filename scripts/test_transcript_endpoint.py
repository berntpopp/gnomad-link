#!/usr/bin/env python3
"""Test our transcript endpoint with the fixed queries."""

import asyncio

import httpx


async def test_transcript_endpoint():
    """Test transcript endpoint."""

    base_url = "http://localhost:8000/api"

    tests = [
        {
            "name": "BRCA1 transcript (GRCh38)",
            "url": f"{base_url}/transcript/ENST00000357654",
            "params": {"reference_genome": "GRCh38"},
        },
        {
            "name": "BRCA1 transcript (GRCh37)",
            "url": f"{base_url}/transcript/ENST00000357654",
            "params": {"reference_genome": "GRCh37"},
        },
        {
            "name": "TP53 transcript",
            "url": f"{base_url}/transcript/ENST00000269305",
            "params": {"reference_genome": "GRCh38"},
        },
        {
            "name": "Invalid transcript",
            "url": f"{base_url}/transcript/INVALID123",
            "params": {"reference_genome": "GRCh38"},
        },
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        for test in tests:
            print(f"\n=== {test['name']} ===")

            try:
                response = await client.get(test["url"], params=test.get("params", {}))

                print(f"Status: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()

                    # Basic fields
                    print(f"transcript_id: {data.get('transcript_id')}")
                    print(f"gene_id: {data.get('gene_id')}")

                    # Gene info
                    if "gene" in data and data["gene"]:
                        print(f"gene.symbol: {data['gene'].get('symbol')}")
                        print(f"gene.name: {data['gene'].get('name')}")

                    # Exons
                    if "exons" in data:
                        print(f"exons count: {len(data['exons'])}")

                    # GTEx expression
                    if (
                        "gtex_tissue_expression" in data
                        and data["gtex_tissue_expression"]
                    ):
                        tissues_with_data = sum(
                            1
                            for v in data["gtex_tissue_expression"].values()
                            if v is not None
                        )
                        print(f"GTEx tissues with data: {tissues_with_data}")

                    # Constraint scores
                    if "gnomad_constraint" in data and data["gnomad_constraint"]:
                        print(f"pLI score: {data['gnomad_constraint'].get('pli')}")

                    # Variants (v3 only)
                    if "variants" in data:
                        print(f"variants count: {len(data['variants'])}")

                else:
                    error_data = response.json()
                    print(f"Error: {error_data.get('detail', 'Unknown error')}")

            except httpx.ConnectError:
                print("Error: Could not connect to server. Make sure it's running.")
            except Exception as e:
                print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_transcript_endpoint())
