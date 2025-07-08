#!/usr/bin/env python3
"""Test GTEx with GRCh37."""

import asyncio

import httpx


async def test_gtex_grch37():
    """Test transcript query with GRCh37."""

    url = "https://gnomad.broadinstitute.org/api/"

    test_query = """
    query {
        transcript(
            transcript_id: "ENST00000357654"
            reference_genome: GRCh37
        ) {
            transcript_id
            reference_genome
            gene_id
            gtex_tissue_expression {
                tissue
                value
            }
        }
    }
    """

    async with httpx.AsyncClient(timeout=30.0) as client:
        print("=== Testing GTEx with GRCh37 ===")
        response = await client.post(
            url,
            json={"query": test_query},
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 200:
            data = response.json()
            if "errors" in data:
                print("Errors:")
                for error in data["errors"]:
                    print(f"  - {error['message']}")
            else:
                print("Success!")
                transcript = data["data"]["transcript"]
                print(f"transcript_id: {transcript['transcript_id']}")
                print(f"reference_genome: {transcript['reference_genome']}")

                if transcript.get("gtex_tissue_expression"):
                    print(f"GTEx tissues: {len(transcript['gtex_tissue_expression'])}")
                    print("First 3 tissues:")
                    for tissue in transcript["gtex_tissue_expression"][:3]:
                        print(f"  - {tissue['tissue']}: {tissue['value']}")
                else:
                    print("No GTEx data")


if __name__ == "__main__":
    asyncio.run(test_gtex_grch37())
