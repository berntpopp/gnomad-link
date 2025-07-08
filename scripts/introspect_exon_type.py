#!/usr/bin/env python3
"""Introspect the Exon type in gnomAD GraphQL API."""

import asyncio

import httpx


async def introspect_exon_type():
    """Get the exact fields available on Exon type."""

    introspection_query = """
    {
      __type(name: "Exon") {
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
            print("=== Exon Type Fields ===")
            if data["data"]["__type"]:
                for field in data["data"]["__type"]["fields"]:
                    field_type = field["type"]
                    type_name = field_type.get("name") or field_type.get(
                        "ofType", {}
                    ).get("name", "Unknown")
                    print(f"  - {field['name']}: {type_name}")

            # Now test with correct fields
            await test_correct_query(client, url)


async def test_correct_query(client: httpx.AsyncClient, url: str):
    """Test transcript query with correct field names."""

    test_query = """
    query {
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
        gene {
          gene_id
          gene_version
          symbol
          name
          hgnc_id
          ncbi_id
          omim_id
        }
        exons {
          feature_type
          start
          stop
        }
        cds_start
        cds_stop
        gtex_tissue_expression {
          adipose_subcutaneous
          adipose_visceral_omentum
          adrenal_gland
        }
      }
    }
    """

    print("\n\n=== Testing Correct Transcript Query ===")
    response = await client.post(
        url, json={"query": test_query}, headers={"Content-Type": "application/json"}
    )

    if response.status_code == 200:
        data = response.json()
        if "errors" in data:
            print("Errors:")
            for error in data["errors"]:
                print(f"  - {error['message']}")
        else:
            print("Success! Sample data:")
            transcript = data["data"]["transcript"]
            print(f"  - transcript_id: {transcript['transcript_id']}")
            print(f"  - gene.symbol: {transcript['gene']['symbol']}")
            print(f"  - exons count: {len(transcript['exons'])}")
            print(f"  - cds_start: {transcript.get('cds_start')}")


if __name__ == "__main__":
    asyncio.run(introspect_exon_type())
