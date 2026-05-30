"""Tests for the base GraphQL client.

Execution now flows through a persistent reconnecting session plus a bounded,
jittered retry layer (see base_client docstring), so query tests mock the
``_execute_with_retry`` seam (or the ``connect_async`` session) rather than the
old one-shot ``execute_async``.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from gnomad_link.api.base_client import (
    BaseGnomadClient,
    DataNotFoundError,
    GnomadApiError,
    RateLimitedError,
    UpstreamInputError,
    VariantNotFoundError,
)


class _FakeSession:
    """Minimal stand-in for a gql reconnecting session."""

    def __init__(self, *, execute: AsyncMock) -> None:
        self.execute = execute


class _FakeLoop:
    """Deterministic clock for retry budget tests."""

    def __init__(self, times: list[float]) -> None:
        self._times = iter(times)

    def time(self) -> float:
        return next(self._times)


class TestBaseGnomadClient:
    """Test base gnomAD client functionality."""

    @pytest.fixture
    def client(self):
        """Create a test client instance."""
        return BaseGnomadClient(api_url="https://test.api.com/graphql")

    @pytest.mark.asyncio
    async def test_execute_query_success(self, client):
        """Test successful query execution."""
        expected_result = {"gene": {"symbol": "TEST"}}

        with (
            patch.object(
                client.query_loader, "load_query", return_value="query { gene { symbol } }"
            ),
            patch.object(
                client.query_builder,
                "process_variables",
                return_value={"gene_id": "ENSG00000123"},
            ),
            patch.object(
                client, "_execute_with_retry", new=AsyncMock(return_value=expected_result)
            ),
        ):
            result = await client.execute_query("gene", {"gene_id": "ENSG00000123"})

            assert result == expected_result

    @pytest.mark.asyncio
    async def test_execute_query_with_graphql_error(self, client):
        """A generic GraphQL error (not 'not found'/validation) becomes GnomadApiError."""
        from gql.transport.exceptions import TransportQueryError

        error = TransportQueryError("Query error", errors=[{"message": "internal failure"}])
        with (
            patch.object(
                client.query_loader, "load_query", return_value="query { variant { id } }"
            ),
            patch.object(client.query_builder, "process_variables", return_value={}),
            patch.object(client, "_execute_with_retry", new=AsyncMock(side_effect=error)),
        ):
            with pytest.raises(GnomadApiError) as exc_info:
                await client.execute_query("variant", {})

            assert "internal failure" in str(exc_info.value)
            # Must NOT be mis-classified as a not-found or input error.
            assert not isinstance(exc_info.value, (DataNotFoundError, UpstreamInputError))

    @pytest.mark.asyncio
    async def test_unrecognized_query_maps_to_upstream_input_error(self, client):
        """A deterministic 'Unrecognized query.' input fault must be non-retryable."""
        from gql.transport.exceptions import TransportQueryError

        error = TransportQueryError(
            "Query error",
            errors=[{"message": "Unrecognized query. Search by variant ID, rsID, or ClinVar ID."}],
        )
        with (
            patch.object(client.query_loader, "load_query", return_value="query { x }"),
            patch.object(client.query_builder, "process_variables", return_value={}),
            patch.object(client, "_execute_with_retry", new=AsyncMock(side_effect=error)),
        ):
            with pytest.raises(UpstreamInputError):
                await client.execute_query("variant_search", {})

    @pytest.mark.asyncio
    async def test_execute_query_network_error(self, client):
        """Test query execution with network errors."""
        from gql.transport.exceptions import TransportError

        with (
            patch.object(client.query_loader, "load_query", return_value="query { gene { id } }"),
            patch.object(client.query_builder, "process_variables", return_value={}),
            patch.object(
                client,
                "_execute_with_retry",
                new=AsyncMock(side_effect=TransportError("Connection failed")),
            ),
        ):
            with pytest.raises(GnomadApiError) as exc_info:
                await client.execute_query("gene", {})

            assert "Connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_persistent_429_maps_to_rate_limited(self, client, monkeypatch):
        """A 429 that survives the retry layer surfaces as RateLimitedError."""
        from gql.transport.exceptions import TransportServerError

        monkeypatch.setattr(asyncio, "sleep", AsyncMock())  # no real backoff delay
        execute = AsyncMock(side_effect=TransportServerError("rate limited", 429))
        connect = AsyncMock(return_value=_FakeSession(execute=execute))

        with (
            patch.object(client.query_loader, "load_query", return_value="query { gene { id } }"),
            patch.object(client.query_builder, "process_variables", return_value={}),
            patch.object(client._client, "connect_async", new=connect),
        ):
            with pytest.raises(RateLimitedError):
                await client.execute_query("gene", {})

        # 5 attempts total before giving up.
        assert execute.call_count == 5
        assert connect.call_count == 1  # session opened exactly once

    @pytest.mark.asyncio
    async def test_retry_succeeds_after_transient_error(self, client, monkeypatch):
        """A transient 503 then success: the call retries and returns the result."""
        from gql.transport.exceptions import TransportServerError

        monkeypatch.setattr(asyncio, "sleep", AsyncMock())
        execute = AsyncMock(
            side_effect=[
                TransportServerError("bad gateway", 503),
                {"gene": {"symbol": "OK"}},
            ]
        )
        connect = AsyncMock(return_value=_FakeSession(execute=execute))

        with (
            patch.object(client.query_loader, "load_query", return_value="query { gene { id } }"),
            patch.object(client.query_builder, "process_variables", return_value={}),
            patch.object(client._client, "connect_async", new=connect),
        ):
            result = await client.execute_query("gene", {})

        assert result == {"gene": {"symbol": "OK"}}
        assert execute.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_reuses_one_queue_wait_budget(self, client, monkeypatch):
        """Retries must share one GNOMAD_QUEUE_WAIT_TIMEOUT budget for slot waits."""
        from gql.transport.exceptions import TransportServerError

        from gnomad_link.config import settings

        monkeypatch.setattr(settings, "GNOMAD_QUEUE_WAIT_TIMEOUT", 10.0)
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())
        monkeypatch.setattr(asyncio, "get_running_loop", lambda: _FakeLoop([100.0, 100.0, 102.0]))
        execute = AsyncMock(
            side_effect=[
                TransportServerError("bad gateway", 503),
                {"gene": {"symbol": "OK"}},
            ]
        )
        acquire_slot = AsyncMock()

        with (
            patch.object(
                client, "_ensure_session", new=AsyncMock(return_value=_FakeSession(execute=execute))
            ),
            patch.object(client, "_acquire_slot", new=acquire_slot),
        ):
            result = await client.execute_query("gene", {})

        assert result == {"gene": {"symbol": "OK"}}
        first_wait = acquire_slot.await_args_list[0].kwargs["timeout"]
        second_wait = acquire_slot.await_args_list[1].kwargs["timeout"]
        assert first_wait == pytest.approx(10.0)
        assert second_wait == pytest.approx(8.0)

    @pytest.mark.asyncio
    async def test_no_retry_on_graphql_query_error(self, client, monkeypatch):
        """GraphQL business errors must NOT retry (one execute call only)."""
        from gql.transport.exceptions import TransportQueryError

        slept = AsyncMock()
        monkeypatch.setattr(asyncio, "sleep", slept)
        execute = AsyncMock(
            side_effect=TransportQueryError("e", errors=[{"message": "Gene not found"}])
        )
        connect = AsyncMock(return_value=_FakeSession(execute=execute))

        with (
            patch.object(client.query_loader, "load_query", return_value="query { gene { id } }"),
            patch.object(client.query_builder, "process_variables", return_value={}),
            patch.object(client._client, "connect_async", new=connect),
        ):
            with pytest.raises(DataNotFoundError):
                await client.execute_query("gene", {})

        assert execute.call_count == 1
        slept.assert_not_called()

    @pytest.mark.asyncio
    async def test_concurrent_queries_share_one_bounded_session(self):
        """Concurrent execute_query calls share one session and respect the cap."""
        client = BaseGnomadClient(api_url="https://test.api.com/graphql", max_concurrency=2)
        state = {"in_flight": 0, "peak": 0}

        async def fake_execute(_doc, variable_values=None):
            state["in_flight"] += 1
            state["peak"] = max(state["peak"], state["in_flight"])
            await asyncio.sleep(0.01)  # overlap window
            state["in_flight"] -= 1
            return {"gene": {"ok": True}}

        connect = AsyncMock(return_value=_FakeSession(execute=AsyncMock(side_effect=fake_execute)))

        with (
            patch.object(client.query_loader, "load_query", return_value="query { gene { id } }"),
            patch.object(client.query_builder, "process_variables", return_value={}),
            patch.object(client._client, "connect_async", new=connect),
        ):
            results = await asyncio.gather(*(client.execute_query("gene", {}) for _ in range(8)))

        assert len(results) == 8
        assert all(r == {"gene": {"ok": True}} for r in results)
        assert connect.call_count == 1  # exactly one session for the whole burst
        assert state["peak"] <= 2  # semaphore bounded concurrency

    @pytest.mark.asyncio
    async def test_queue_saturation_returns_rate_limited(self, monkeypatch):
        """When the concurrency slot can't be acquired in time, callers get a fast,
        retryable RateLimitedError (backpressure) rather than an opaque hang."""
        from gnomad_link.config import settings

        monkeypatch.setattr(settings, "GNOMAD_QUEUE_WAIT_TIMEOUT", 0.05)
        client = BaseGnomadClient(api_url="https://test.api.com/graphql", max_concurrency=1)
        holding = asyncio.Event()

        async def slow_execute(_doc, variable_values=None):
            holding.set()
            await asyncio.sleep(0.5)  # hold the only slot past the queue-wait window
            return {"gene": {"ok": True}}

        connect = AsyncMock(return_value=_FakeSession(execute=AsyncMock(side_effect=slow_execute)))
        with (
            patch.object(client.query_loader, "load_query", return_value="query { gene { id } }"),
            patch.object(client.query_builder, "process_variables", return_value={}),
            patch.object(client._client, "connect_async", new=connect),
        ):
            first = asyncio.create_task(client.execute_query("gene", {}))
            await holding.wait()  # the only slot is now held
            with pytest.raises(RateLimitedError):
                await client.execute_query("gene", {})  # waits 0.05s -> saturated
            assert await first == {"gene": {"ok": True}}
        await client.close()

    @pytest.mark.asyncio
    async def test_close_without_session_closes_transport(self, client):
        """When no session was opened, close() falls back to closing the transport."""
        with patch.object(client, "_transport") as mock_transport:
            mock_transport.close = AsyncMock()
            await client.close()
            mock_transport.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_with_session_is_idempotent(self, client):
        """close() closes the session once and is safe to call again."""
        client._session = object()  # pretend a session is open
        close_async = AsyncMock()
        with patch.object(client._client, "close_async", new=close_async):
            await client.close()
            await client.close()  # second call must not error
        assert close_async.call_count == 1
        assert client._session is None

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

    def test_upstream_input_error_is_api_error(self):
        """UpstreamInputError must subclass GnomadApiError so broad excepts catch it."""
        error = UpstreamInputError("Unrecognized query.")
        assert isinstance(error, GnomadApiError)

    def test_rate_limited_error_is_api_error(self):
        """RateLimitedError must subclass GnomadApiError."""
        error = RateLimitedError("429")
        assert isinstance(error, GnomadApiError)

    @pytest.mark.asyncio
    async def test_client_initialization_custom_url(self):
        """Test client initialization with custom URL."""
        client = BaseGnomadClient(api_url="https://custom.api.com/graphql")
        assert client.api_url == "https://custom.api.com/graphql"
        await client.close()

    @pytest.mark.asyncio
    async def test_query_with_empty_result(self, client):
        """An upstream null payload must raise DataNotFoundError."""
        with (
            patch.object(
                client.query_loader, "load_query", return_value="query { variant { id } }"
            ),
            patch.object(client.query_builder, "process_variables", return_value={}),
            patch.object(
                client, "_execute_with_retry", new=AsyncMock(return_value={"variant": None})
            ),
        ):
            with pytest.raises(DataNotFoundError):
                await client.execute_query("variant", {})

    @pytest.mark.asyncio
    async def test_context_manager(self, client):
        """Test async context manager."""
        with patch.object(client, "close") as mock_close:
            mock_close.return_value = AsyncMock()
            async with client as ctx_client:
                assert ctx_client is client
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_data_not_found_in_error(self, client):
        """Test data not found detection in GraphQL errors."""
        from gql.transport.exceptions import TransportQueryError

        error = TransportQueryError("Query error", errors=[{"message": "Gene not found"}])
        with (
            patch.object(client.query_loader, "load_query", return_value="query { gene { id } }"),
            patch.object(client.query_builder, "process_variables", return_value={}),
            patch.object(client, "_execute_with_retry", new=AsyncMock(side_effect=error)),
        ):
            with pytest.raises(DataNotFoundError) as exc_info:
                await client.execute_query("gene", {})

            assert "Gene not found" in str(exc_info.value)

    def test_gnomad_api_error(self):
        """Test GnomadApiError creation."""
        error = GnomadApiError("API error occurred")
        assert str(error) == "API error occurred"
        assert isinstance(error, Exception)
