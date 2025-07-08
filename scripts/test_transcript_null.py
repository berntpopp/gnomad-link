#!/usr/bin/env python3
"""Test if gnomAD returns null for non-existent transcript."""

import asyncio

import httpx


async def test_null_transcript():
    """Test various transcript IDs to see responses."""

    test_cases = [
        ("Valid transcript", "ENST00000357654"),
        ("Invalid format", "INVALID123"),
        ("Non-existent but valid format", "ENST99999999999"),
        ("Short invalid", "ENST123"),
    ]

    url = "https://gnomad.broadinstitute.org/api/"

    async with httpx.AsyncClient(timeout=10.0) as client:
        for name, transcript_id in test_cases:
            print(f"\n=== {name}: {transcript_id} ===")

            query = f"""
            query {{
                transcript(
                    transcript_id: "{transcript_id}"
                    reference_genome: GRCh38
                ) {{
                    transcript_id
                }}
            }}
            """

            try:
                response = await client.post(
                    url,
                    json={"query": query},
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200:
                    data = response.json()
                    if "errors" in data:
                        print(f"GraphQL Errors: {data['errors']}")
                    elif "data" in data:
                        transcript_data = data["data"]["transcript"]
                        if transcript_data is None:
                            print("Result: null (transcript not found)")
                        else:
                            print(
                                f"Result: Found transcript {transcript_data['transcript_id']}"
                            )
                else:
                    print(f"HTTP Error: {response.status_code}")
            except httpx.TimeoutException:
                print("Timeout!")
            except Exception as e:
                print(f"Error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(test_null_transcript())
