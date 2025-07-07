"""Base GraphQL client with centralized query management."""

import logging
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportError, TransportQueryError

from gnomad_mcp.config import settings
from gnomad_mcp.graphql import QueryLoader, QueryBuilder

logger = logging.getLogger(__name__)


class GnomadApiError(Exception):
    """Base exception for gnomAD API errors."""

    pass


class VariantNotFoundError(GnomadApiError):
    """Raised when a variant is not found in the database."""

    pass


class DataNotFoundError(GnomadApiError):
    """Raised when requested data is not found."""

    pass


class BaseGnomadClient(ABC):
    """Base client for gnomAD GraphQL API."""

    def __init__(self, api_url: Optional[str] = None):
        """Initialize the API client.

        Args:
            api_url: Override the API URL from settings.
        """
        self.api_url = api_url or settings.GNOMAD_API_URL
        self._transport = AIOHTTPTransport(
            url=self.api_url,
            timeout=30,
            ssl=True,
        )
        self._client = Client(
            transport=self._transport,
            fetch_schema_from_transport=False,
        )
        self.query_loader = QueryLoader()
        self.query_builder = QueryBuilder()

    async def execute_query(
        self, query_name: str, variables: Dict[str, Any], version: str = "v4"
    ) -> Dict[str, Any]:
        """Execute a GraphQL query.

        Args:
            query_name: Name of the query to execute
            variables: Query variables
            version: API version

        Returns:
            Query result

        Raises:
            GnomadApiError: On API errors
        """
        try:
            # Load query
            query_string = self.query_loader.load_query(query_name, version)

            # Process variables
            processed_vars = self.query_builder.process_variables(
                query_name, variables, version
            )

            # Execute
            query_doc = gql(query_string)
            result = await self._client.execute_async(
                query_doc, variable_values=processed_vars
            )

            # Check if data was found
            if query_name in result and result[query_name] is None:
                raise DataNotFoundError(
                    f"No data found for {query_name} with parameters: {processed_vars}"
                )

            return result

        except TransportQueryError as e:
            if e.errors:
                error_msg = "; ".join(
                    [err.get("message", str(err)) for err in e.errors]
                )
                raise GnomadApiError(f"GraphQL error: {error_msg}") from e
            raise GnomadApiError(f"Query error: {str(e)}") from e
        except TransportError as e:
            raise GnomadApiError(f"API request failed: {str(e)}") from e
        except FileNotFoundError as e:
            raise GnomadApiError(f"Query not found: {str(e)}") from e
        except Exception as e:
            if isinstance(e, GnomadApiError):
                raise
            raise GnomadApiError(f"Unexpected error: {str(e)}") from e

    async def close(self):
        """Close the client connection."""
        await self._transport.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
