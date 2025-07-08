#!/usr/bin/env python3
"""Introspect GtexTissue type structure."""

import asyncio
import json

import httpx


async def introspect_gtex():
    """Find out the correct structure for GTEx data."""

    # First, introspect the GtexTissue type
    introspection_query = """
    {
      __type(name: "GtexTissue") {
        name
        kind
        description
        fields {
          name
          description
          type {
            name
            kind
            ofType {
              name
              kind
            }
          }
        }
      }
    }
    """

    url = "https://gnomad.broadinstitute.org/api/"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            json={"query": introspection_query},
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 200:
            data = response.json()
            print("=== GtexTissue Type Fields ===")
            if data["data"]["__type"]:
                print(f"Type: {data['data']['__type']['name']}")
                print("Fields:")
                for field in data["data"]["__type"]["fields"]:
                    field_type = field["type"]
                    type_name = field_type.get("name") or field_type.get(
                        "ofType", {}
                    ).get("name", "Unknown")
                    print(f"  - {field['name']}: {type_name}")

            # Now test the correct query structure
            await test_correct_gtex_query(client, url)


async def test_correct_gtex_query(client: httpx.AsyncClient, url: str):
    """Test transcript query with correct GTEx structure."""

    # Test if GTEx is an array or object
    test_query = """
    query {
        transcript(
            transcript_id: "ENST00000357654"
            reference_genome: GRCh38
        ) {
            transcript_id
            gtex_tissue_expression {
                tissue
                value
            }
        }
    }
    """

    print("\n\n=== Testing GTEx Query ===")
    response = await client.post(
        url, json={"query": test_query}, headers={"Content-Type": "application/json"}
    )

    if response.status_code == 200:
        data = response.json()
        if "errors" in data:
            print("Errors:")
            for error in data["errors"]:
                print(f"  - {error['message']}")

            # Try another structure
            print("\n\nTrying transcript GTEx as an object...")
            await test_gtex_as_object(client, url)
        else:
            print("Success! GTEx data structure:")
            if data["data"]["transcript"]["gtex_tissue_expression"]:
                print(
                    json.dumps(
                        data["data"]["transcript"]["gtex_tissue_expression"][:3],
                        indent=2,
                    )
                )


async def test_gtex_as_object(client: httpx.AsyncClient, url: str):
    """Test if GTEx at transcript level might be different."""

    # Check what fields transcript actually has
    introspection_query = """
    {
      __type(name: "Transcript") {
        name
        fields {
          name
          type {
            name
            kind
            ofType {
              name
              kind
            }
          }
        }
      }
    }
    """

    response = await client.post(
        url,
        json={"query": introspection_query},
        headers={"Content-Type": "application/json"},
    )

    if response.status_code == 200:
        data = response.json()
        print("\n=== Transcript Type Fields (filtered for gtex) ===")
        for field in data["data"]["__type"]["fields"]:
            if "gtex" in field["name"].lower() or "expression" in field["name"].lower():
                field_type = field["type"]
                type_name = field_type.get("name") or field_type.get("ofType", {}).get(
                    "name", "Unknown"
                )
                print(f"  - {field['name']}: {type_name}")


if __name__ == "__main__":
    asyncio.run(introspect_gtex())
