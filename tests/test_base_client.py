"""Tests for the base GraphQL client."""

from unittest.mock import AsyncMock, patch

import pytest

from gnomad_link.api.base_client import (
    BaseGnomadClient,
    DataNotFoundError,
    GnomadApiError,
    VariantNotFoundError,
)


class TestBaseGnomadClient:
    """Test base gnomAD client functionality."""

    @pytest.fixture
    def client(self):
        """Create a test client instance."""
        return BaseGnomadClient(api_url="https://test.api.com/graphql")

    @pytest.mark.asyncio
    async def test_execute_query_success(self, client):
        """Test successful query execution."""
        query_name = "gene"
        variables = {"gene_id": "ENSG00000123"}
        expected_result = {"gene": {"symbol": "TEST"}}

        with patch.object(client, "_client") as mock_client:
            with patch.object(
                client.query_loader,
                "load_query",
                return_value="query { gene { symbol } }",
            ):
                with patch.object(
                    client.query_builder, "process_variables", return_value=variables
                ):
                    mock_execute = AsyncMock(return_value=expected_result)
                    mock_client.execute_async = mock_execute

                    result = await client.execute_query(query_name, variables)

                    assert result == expected_result
                    mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_query_with_errors(self, client):
        """Test query execution with GraphQL errors."""
        from gql.transport.exceptions import TransportQueryError

        query_name = "variant"
        variables = {"variant_id": "1-12345-A-G"}

        with patch.object(
            client.query_loader, "load_query", return_value="query { variant { id } }"
        ):
            with patch.object(
                client.query_builder, "process_variables", return_value=variables
            ):
                with patch.object(client, "_client") as mock_client:
                    # Simulate GraphQL errors
                    error = TransportQueryError(
                        "Query error", errors=[{"message": "Field not found"}]
                    )
                    mock_execute = AsyncMock(side_effect=error)
                    mock_client.execute_async = mock_execute

                    with pytest.raises(GnomadApiError) as exc_info:
                        await client.execute_query(query_name, variables)

                    assert "Field not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_query_network_error(self, client):
        """Test query execution with network errors."""
        from gql.transport.exceptions import TransportError

        query_name = "gene"

        with patch.object(
            client.query_loader, "load_query", return_value="query { gene { id } }"
        ):
            with patch.object(
                client.query_builder, "process_variables", return_value={}
            ):
                with patch.object(client, "_client") as mock_client:
                    # Simulate network error
                    mock_execute = AsyncMock(
                        side_effect=TransportError("Connection failed")
                    )
                    mock_client.execute_async = mock_execute

                    with pytest.raises(GnomadApiError) as exc_info:
                        await client.execute_query(query_name, {})

                    assert "Connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_close(self, client):
        """Test client cleanup."""
        with patch.object(client, "_transport") as mock_transport:
            mock_close = AsyncMock()
            mock_transport.close = mock_close

            await client.close()

            mock_close.assert_called_once()

    def test_data_not_found_error(self):
        """Test DataNotFoundError creation."""
        error = DataNotFoundError("Gene not found")
        assert str(error) == "Gene not found"
        assert isinstance(error, Exception)

    def test_variant_not_found_error(self):
        """Test VariantNotFoundError creation."""
        error = VariantNotFoundError("Variant 1-12345-A-G not found")
        assert "1-12345-A-G" in str(error)
        assert isinstance(error, DataNotFoundError)

    def test_gnomad_api_error(self):
        """Test GnomadApiError creation."""
        error = GnomadApiError("API error occurred")
        assert str(error) == "API error occurred"
        assert isinstance(error, Exception)

    @pytest.mark.asyncio
    async def test_client_initialization_custom_url(self):
        """Test client initialization with custom URL."""
        client = BaseGnomadClient(api_url="https://custom.api.com/graphql")

        assert client.api_url == "https://custom.api.com/graphql"

        await client.close()

    @pytest.mark.asyncio
    async def test_query_with_empty_result(self, client):
        """Test handling of empty query results."""
        query_name = "variant"
        variables = {"variant_id": "nonexistent"}

        with patch.object(
            client.query_loader, "load_query", return_value="query { variant { id } }"
        ):
            with patch.object(
                client.query_builder, "process_variables", return_value=variables
            ):
                with patch.object(client, "_client") as mock_client:
                    # Return None/empty result - should raise DataNotFoundError
                    mock_execute = AsyncMock(return_value={"variant": None})
                    mock_client.execute_async = mock_execute

                    with pytest.raises(DataNotFoundError):
                        await client.execute_query(query_name, variables)

    @pytest.mark.asyncio
    async def test_context_manager(self, client):
        """Test async context manager."""
        with patch.object(client, "close") as mock_close:
            mock_close.return_value = AsyncMock()

            async with client as ctx_client:
                assert ctx_client is client

            # close should be called on exit
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_data_not_found_in_error(self, client):
        """Test data not found detection in GraphQL errors."""
        from gql.transport.exceptions import TransportQueryError

        query_name = "gene"
        variables = {"gene_symbol": "FAKEGENE"}

        with patch.object(
            client.query_loader, "load_query", return_value="query { gene { id } }"
        ):
            with patch.object(
                client.query_builder, "process_variables", return_value=variables
            ):
                with patch.object(client, "_client") as mock_client:
                    # Simulate "not found" error
                    error = TransportQueryError(
                        "Query error", errors=[{"message": "Gene not found"}]
                    )
                    mock_execute = AsyncMock(side_effect=error)
                    mock_client.execute_async = mock_execute

                    with pytest.raises(DataNotFoundError) as exc_info:
                        await client.execute_query(query_name, variables)

                    assert "Gene not found" in str(exc_info.value)
