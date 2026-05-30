"""Base GraphQL client with centralized query management."""

import logging

# Removed ABC import as class has no abstract methods
from typing import Any

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportError, TransportQueryError

from gnomad_link.config import settings
from gnomad_link.graphql import QueryBuilder, QueryLoader

logger = logging.getLogger(__name__)


class GnomadApiError(Exception):
    """Base exception for gnomAD API errors."""

    pass


class DataNotFoundError(GnomadApiError):
    """Raised when requested data is not found."""

    pass


class VariantNotFoundError(DataNotFoundError):
    """Raised when a variant is not found in the database."""

    pass


class BaseGnomadClient:
    """Base client for gnomAD GraphQL API."""

    def __init__(self, api_url: str | None = None):
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
        self,
        query_name: str,
        variables: dict[str, Any],
        version: str = "v4",
        operation_name: str | None = None,
    ) -> dict[str, Any]:
        """Execute a GraphQL query.

        Args:
            query_name: Name of the query to execute
            variables: Query variables
            version: API version
            operation_name: Named operation to select in a multi-op document

        Returns:
            Query result

        Raises:
            GnomadApiError: On API errors
        """
        try:
            # Load query
            query_string = self.query_loader.load_query(query_name, version)

            # Process variables
            processed_vars = self.query_builder.process_variables(query_name, variables, version)

            # Execute
            query_doc = gql(query_string)
            if operation_name is not None:
                result = await self._client.execute_async(
                    query_doc,
                    variable_values=processed_vars,
                    operation_name=operation_name,
                )
            else:
                result = await self._client.execute_async(query_doc, variable_values=processed_vars)

            # Check if data was found (single-op queries are keyed by query_name).
            if operation_name is None and query_name in result and result[query_name] is None:
                raise DataNotFoundError(
                    f"No data found for {query_name} with parameters: {processed_vars}"
                )

            return result

        except TransportQueryError as e:
            if e.errors:
                error_msg = "; ".join([err.get("message", str(err)) for err in e.errors])
                # Check for "not found" errors
                if any("not found" in err.get("message", "").lower() for err in e.errors):
                    raise DataNotFoundError(error_msg) from e
                raise GnomadApiError(f"GraphQL error: {error_msg}") from e
            raise GnomadApiError(f"Query error: {e!s}") from e
        except TransportError as e:
            raise GnomadApiError(f"API request failed: {e!s}") from e
        except FileNotFoundError as e:
            raise GnomadApiError(f"Query not found: {e!s}") from e
        except Exception as e:
            if isinstance(e, GnomadApiError):
                raise
            raise GnomadApiError(f"Unexpected error: {e!s}") from e

    async def close(self) -> None:
        """Close the client connection."""
        await self._transport.close()

    async def __aenter__(self) -> "BaseGnomadClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
