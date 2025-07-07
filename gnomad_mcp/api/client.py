"""GraphQL client for interacting with the gnomAD API."""

from functools import cache
from pathlib import Path
from typing import Dict, Any, Optional

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportError

from gnomad_mcp.config import settings


class GnomadApiError(Exception):
    """Base exception for gnomAD API errors."""

    pass


class VariantNotFoundError(GnomadApiError):
    """Raised when a variant is not found in the database."""

    pass


@cache
def _load_query(filename: str) -> str:
    """Load a GraphQL query from file with simple import handling.

    Args:
        filename: Name of the query file to load.

    Returns:
        The query string with imports resolved.
    """
    queries_dir = Path(__file__).parent / "queries"
    query_path = queries_dir / filename

    with open(query_path, "r") as f:
        content = f.read()

    # Simple import handling - replace import directive with fragment content
    if "#import" in content:
        fragment_content = _load_query("fragments.graphql")
        content = content.replace('#import "./fragments.graphql"', fragment_content)

    return content


class GnomadApiClient:
    """Client for interacting with the gnomAD GraphQL API."""

    def __init__(self, api_url: Optional[str] = None):
        """Initialize the API client.

        Args:
            api_url: Override the API URL from settings.
        """
        self.api_url = api_url or settings.GNOMAD_API_URL
        self._transport = AIOHTTPTransport(
            url=self.api_url,
            timeout=30,  # 30 second timeout
            ssl=True,  # Enable SSL certificate verification
        )
        self._client = Client(
            transport=self._transport,
            # Skip schema introspection for performance
            fetch_schema_from_transport=False,
        )

        # Pre-load and parse queries
        self.variant_query = gql(_load_query("variant.graphql"))

    async def get_variant(self, variant_id: str, dataset: str) -> Dict[str, Any]:
        """Fetch variant data from gnomAD.

        Args:
            variant_id: The variant identifier (e.g., "1-55039447-G-T").
            dataset: The dataset to query (e.g., "gnomad_r4").

        Returns:
            Raw variant data from the API.

        Raises:
            VariantNotFoundError: If the variant is not found.
            GnomadApiError: For other API errors.
        """
        params = {
            "variantId": variant_id,
            "dataset": dataset,
        }

        try:
            result = await self._client.execute_async(
                self.variant_query,
                variable_values=params,
            )

            # Check if variant was found
            if not result.get("variant"):
                raise VariantNotFoundError(
                    f"Variant {variant_id} not found in dataset {dataset}"
                )

            return result

        except TransportError as e:
            # Handle transport-level errors
            raise GnomadApiError(f"API request failed: {str(e)}") from e
        except Exception as e:
            # Re-raise our custom errors
            if isinstance(e, GnomadApiError):
                raise
            # Wrap unexpected errors
            raise GnomadApiError(f"Unexpected error: {str(e)}") from e

    async def close(self):
        """Close the client connection."""
        await self._transport.close()
