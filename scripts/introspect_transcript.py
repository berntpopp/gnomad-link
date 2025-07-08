#!/usr/bin/env python3
"""Introspect gnomAD GraphQL API for transcript-related queries."""

import asyncio
import json

import httpx


async def introspect_transcript_schema():
    """Introspect the gnomAD GraphQL API for transcript-related types and queries."""

    # Introspection query for transcript-related information
    introspection_query = """
    {
      __schema {
        queryType {
          fields {
            name
            description
            args {
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
        types {
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
                ofType {
                  name
                  kind
                }
              }
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

            # Find transcript-related queries
            print("=== TRANSCRIPT-RELATED QUERIES ===")
            query_fields = data["data"]["__schema"]["queryType"]["fields"]
            for field in query_fields:
                if "transcript" in field["name"].lower():
                    print(f"\nQuery: {field['name']}")
                    print(f"Description: {field.get('description', 'No description')}")
                    print("Arguments:")
                    for arg in field.get("args", []):
                        arg_type = arg["type"]
                        type_name = arg_type.get("name") or arg_type.get(
                            "ofType", {}
                        ).get("name", "Unknown")
                        print(f"  - {arg['name']}: {type_name}")
                    return_type = field["type"]
                    return_name = return_type.get("name") or return_type.get(
                        "ofType", {}
                    ).get("name", "Unknown")
                    print(f"Returns: {return_name}")

            # Find Transcript type definition
            print("\n\n=== TRANSCRIPT TYPE DEFINITION ===")
            types = data["data"]["__schema"]["types"]
            for type_def in types:
                if type_def["name"] == "Transcript":
                    print(f"\nType: {type_def['name']}")
                    print(
                        f"Description: {type_def.get('description', 'No description')}"
                    )
                    if type_def.get("fields"):
                        print("Fields:")
                        for field in type_def["fields"][
                            :20
                        ]:  # Limit to first 20 fields
                            field_type = field["type"]
                            type_name = "Unknown"
                            if field_type.get("name"):
                                type_name = field_type["name"]
                            elif field_type.get("ofType", {}).get("name"):
                                type_name = field_type["ofType"]["name"]
                            elif (
                                field_type.get("ofType", {})
                                .get("ofType", {})
                                .get("name")
                            ):
                                type_name = (
                                    f"[{field_type['ofType']['ofType']['name']}]"
                                )
                            print(f"  - {field['name']}: {type_name}")
                    break

            # Test actual transcript query
            print("\n\n=== TESTING TRANSCRIPT QUERY ===")
            await test_transcript_query(client, url)

        else:
            print(f"Error: {response.status_code}")
            print(response.text)


async def test_transcript_query(client: httpx.AsyncClient, url: str):
    """Test an actual transcript query."""

    # Test with BRCA1 transcript
    test_query = """
    query TranscriptTest {
      transcript(
        transcript_id: "ENST00000357654"
        reference_genome: GRCh38
      ) {
        transcript_id
        transcript_version
        reference_genome
        chrom
        start
        stop
        strand
        gene_id
        gene_symbol
        is_canonical
        exons {
          exon_id
          chrom
          start
          stop
          strand
          feature_type
        }
      }
    }
    """

    response = await client.post(
        url, json={"query": test_query}, headers={"Content-Type": "application/json"}
    )

    if response.status_code == 200:
        data = response.json()
        if "errors" in data:
            print("Query returned errors:")
            for error in data["errors"]:
                print(f"  - {error.get('message', 'Unknown error')}")
        elif "data" in data and data["data"].get("transcript"):
            print("Query successful! Sample fields:")
            transcript = data["data"]["transcript"]
            print(f"  - transcript_id: {transcript.get('transcript_id')}")
            print(f"  - gene_symbol: {transcript.get('gene_symbol')}")
            print(f"  - is_canonical: {transcript.get('is_canonical')}")
            print(f"  - number of exons: {len(transcript.get('exons', []))}")
        else:
            print("Query returned no data")
            print(json.dumps(data, indent=2))
    else:
        print(f"HTTP Error: {response.status_code}")


async def test_v2_transcript():
    """Test v2 transcript query."""
    print("\n\n=== TESTING V2 TRANSCRIPT QUERY ===")

    v2_query = """
    query TranscriptV2Test {
      transcript(
        transcript_id: "ENST00000357654"
        reference_genome: GRCh37
        dataset: gnomad_r2_1
      ) {
        transcript_id
        transcript_version
        chrom
        start
        stop
        strand
        gene_id
      }
    }
    """

    url = "https://gnomad.broadinstitute.org/api/"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url, json={"query": v2_query}, headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            data = response.json()
            if "errors" in data:
                print("V2 Query returned errors:")
                for error in data["errors"]:
                    print(f"  - {error.get('message', 'Unknown error')}")
            else:
                print("V2 Query result:")
                print(json.dumps(data, indent=2))


if __name__ == "__main__":
    asyncio.run(introspect_transcript_schema())
