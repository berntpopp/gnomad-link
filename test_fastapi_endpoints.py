#!/usr/bin/env python
"""Test all FastAPI endpoints."""

import asyncio
import httpx

BASE_URL = "http://127.0.0.1:8000"


async def test_endpoints():
    """Test all the FastAPI endpoints."""
    async with httpx.AsyncClient() as client:
        print("Testing FastAPI Endpoints\n")

        # Test 1: Root endpoint
        print("1. Testing root endpoint:")
        response = await client.get(f"{BASE_URL}/")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Version: {data.get('version')}")
            print(f"   Endpoints: {len(data.get('endpoints', {}))} categories")

        # Test 2: Variant lookup
        print("\n2. Testing variant lookup:")
        response = await client.get(f"{BASE_URL}/variant/gnomad_r4/1-55039447-G-T")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Variant ID: {data.get('variant_id')}")
            print(f"   Has exome data: {'exome_frequencies' in data}")
            print(f"   Has genome data: {'genome_frequencies' in data}")

        # Test 3: Gene search
        print("\n3. Testing gene search:")
        response = await client.get(f"{BASE_URL}/search/gene?query=BRCA1")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Found {len(data)} genes")
            if data:
                print(
                    f"   First result: {data[0].get('symbol')} ({data[0].get('ensembl_id')})"
                )

        # Test 4: Gene lookup
        print("\n4. Testing gene lookup:")
        response = await client.get(f"{BASE_URL}/gene/?gene_symbol=BRCA1")
        print(f"   Status: {response.status_code}")
        gene_id = None
        if response.status_code == 200:
            data = response.json()
            gene_id = data.get("gene_id")
            print(f"   Gene: {data.get('gene_symbol')} ({gene_id})")

        # Test 4b: Gene variants
        if gene_id:
            print("\n4b. Testing gene variants:")
            response = await client.get(f"{BASE_URL}/gene/variants/{gene_id}")
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Found {data.get('variant_count')} variants")

        # Test 5: ClinVar variant
        print("\n5. Testing ClinVar variant:")
        response = await client.get(f"{BASE_URL}/clinvar/variant/1-55039447-G-T")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Clinical significance: {data.get('clinical_significance')}")

        # Test 6: Region query
        print("\n6. Testing region query:")
        response = await client.get(
            f"{BASE_URL}/region/?chrom=1&start=55039000&stop=55040000"
        )
        print(f"   Status: {response.status_code}")

        # Test 7: Health check
        print("\n7. Testing health check:")
        response = await client.get(f"{BASE_URL}/health")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Health: {response.json().get('status')}")

        # Test 8: Cache stats
        print("\n8. Testing cache stats:")
        response = await client.get(f"{BASE_URL}/cache/stats")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            stats = response.json()
            print(f"   Cache hits: {stats.get('hits', 0)}")
            print(f"   Cache misses: {stats.get('misses', 0)}")

        print("\n✅ All endpoint tests complete!")


if __name__ == "__main__":
    print("Make sure the FastAPI server is running on port 8000")
    print("You can start it with: python server.py")
    print()
    asyncio.run(test_endpoints())
