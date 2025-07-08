#!/usr/bin/env python3
"""Test the liftover endpoint manually."""

import asyncio
import os

import httpx

# Bypass proxy for localhost
os.environ["NO_PROXY"] = "localhost,127.0.0.1"


async def test_liftover_endpoint():
    """Test the /api/liftover/ endpoint."""
    async with httpx.AsyncClient() as client:
        base_url = "http://localhost:8000"

        print("Testing Liftover Endpoint")
        print("=" * 60)

        # Test 1: Forward liftover
        print("\nTest 1: Forward liftover (GRCh37 → GRCh38)")
        try:
            params = {
                "source_variant_id": "17-7577121-G-A",  # TP53 in GRCh37
                "reference_genome": "GRCh38",
            }
            response = await client.get(f"{base_url}/liftover/", params=params)

            if response.status_code == 200:
                data = response.json()
                print("✓ Success!")
                print(f"  Query type: {data['query_type']}")
                print(f"  Results count: {len(data['results'])}")
                if data["results"]:
                    for i, result in enumerate(data["results"]):
                        print(f"  Result {i+1}:")
                        print(f"    Source: {result['source']}")
                        print(f"    Liftover: {result['liftover']}")
                        print(f"    Datasets: {result.get('datasets', [])}")
                else:
                    print("  No liftover mapping found")
            else:
                print(f"✗ Failed with status {response.status_code}: {response.text}")

        except httpx.ConnectError:
            print("✗ Error: Could not connect to server. Run: make run-dev")
        except Exception as e:
            print(f"✗ Error: {type(e).__name__}: {e}")

        # Test 2: Test with real variant (GRCh37 to GRCh38)
        print("\nTest 2: Liftover GRCh37 → GRCh38 (expected result)")
        try:
            params = {
                "source_variant_id": "17-7577121-G-A",
                "reference_genome": "GRCh37",
            }
            response = await client.get(f"{base_url}/liftover/", params=params)

            if response.status_code == 200:
                data = response.json()
                print("✓ Success!")
                print(f"  Query type: {data['query_type']}")
                print(f"  Results count: {len(data['results'])}")
                if data["results"]:
                    for i, result in enumerate(data["results"]):
                        print(f"  Result {i+1}:")
                        print(f"    Source: {result['source']}")
                        print(f"    Liftover: {result['liftover']}")
                        print(f"    Datasets: {result.get('datasets', [])}")
                else:
                    print("  No liftover mapping found")
            else:
                print(f"✗ Failed: {response.text}")

        except Exception as e:
            print(f"✗ Error: {type(e).__name__}: {e}")

        # Test 3: Error case (missing source_variant_id)
        print("\nTest 3: Error case (missing source_variant_id)")
        try:
            params = {
                "reference_genome": "GRCh38",
            }
            response = await client.get(f"{base_url}/liftover/", params=params)

            if response.status_code == 422:
                print("✓ Correctly returned error 422 (validation error)")
            else:
                print(f"✗ Unexpected status: {response.status_code}")

        except Exception as e:
            print(f"✗ Error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(test_liftover_endpoint())
