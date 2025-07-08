#!/usr/bin/env python3
"""Test the ClinVar meta endpoint."""

import asyncio

import httpx


async def test_clinvar_meta():
    """Test the /api/clinvar/meta endpoint."""
    async with httpx.AsyncClient() as client:
        try:
            # Test the meta endpoint
            print("Testing /api/clinvar/meta endpoint...")
            response = await client.get("http://localhost:8000/api/clinvar/meta")

            if response.status_code == 200:
                data = response.json()
                print(f"✓ Success! Response: {data}")
                print(f"  ClinVar release date: {data.get('clinvar_release_date')}")
            else:
                print(f"✗ Failed with status {response.status_code}: {response.text}")

        except httpx.ConnectError:
            print("✗ Error: Could not connect to server. Is the server running?")
            print("  Run: make run-dev")
        except Exception as e:
            print(f"✗ Error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(test_clinvar_meta())
