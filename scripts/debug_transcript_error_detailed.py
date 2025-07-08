#!/usr/bin/env python3
"""Debug transcript error in detail."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gql import gql

from gnomad_mcp.api.base_client import BaseGnomadClient


async def debug_transcript_error():
    """Debug the exact error flow."""

    client = BaseGnomadClient()

    # Test with the exact query our system uses
    query_string = """
query transcript($transcript_id: String!, $reference_genome: ReferenceGenomeId!) {
    transcript(transcript_id: $transcript_id, reference_genome: $reference_genome) {
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
            canonical_transcript_id
            mane_select_transcript {
                ensembl_id
                ensembl_version
                refseq_id
                refseq_version
            }
        }
        exons {
            feature_type
            start
            stop
        }
    }
}
"""

    variables = {"transcript_id": "ENST99999999999", "reference_genome": "GRCh38"}

    try:
        print("Executing query...")
        query_doc = gql(query_string)
        result = await client._client.execute_async(
            query_doc, variable_values=variables
        )
        print(f"Result: {result}")
    except Exception as e:
        print(f"Exception type: {type(e).__name__}")
        print(f"Exception: {e}")

        # Check if it has errors attribute
        if hasattr(e, "errors"):
            print(f"Errors: {e.errors}")

        # Test if our error handling would catch it
        from gql.transport.exceptions import TransportQueryError

        if isinstance(e, TransportQueryError):
            print("This is a TransportQueryError")
            if e.errors:
                error_msg = "; ".join(err.get("message", str(err)) for err in e.errors)
                print(f"Error message: {error_msg}")

                # Check for "not found" errors
                if any(
                    "not found" in err.get("message", "").lower() for err in e.errors
                ):
                    print("Would be caught as DataNotFoundError")
                else:
                    print("Would be caught as GnomadApiError")

    await client.close()


if __name__ == "__main__":
    asyncio.run(debug_transcript_error())
