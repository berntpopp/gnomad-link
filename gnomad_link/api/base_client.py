"""Base GraphQL client with centralized query management.

Concurrency model: one persistent reconnecting gql session per client, opened
lazily under a double-checked lock and reused across all concurrent tasks. The
one-shot ``Client.execute_async`` connects AND closes the shared transport on
every call, so two concurrent calls race into ``TransportAlreadyConnected``; a
single connected aiohttp session is safe for concurrent ``execute`` and gives
true HTTP parallelism. An ``asyncio.Semaphore`` bounds burst pressure on the
upstream rate limiter and a jittered retry layer absorbs residual 429s and
transient transport faults.
"""

import asyncio
import logging
import random
from typing import Any

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import (
    TransportClosed,
    TransportError,
    TransportQueryError,
    TransportServerError,
)

from gnomad_link.config import settings
from gnomad_link.graphql import QueryBuilder, QueryLoader

logger = logging.getLogger(__name__)

# Upstream GraphQL messages that indicate a DETERMINISTIC, non-retryable input
# fault (wrong identifier shape, gene symbol passed to a variant tool, malformed
# query). These are GraphQL validation-shaped phrases and are always client-side,
# so the caller must reformulate rather than retry. Matched case-insensitively as
# substrings; kept GraphQL-validation-specific to avoid stranding transient faults.
_INPUT_ERROR_SIGNALS = (
    "unrecognized query",
    "cannot query field",
    "unknown argument",
    "syntax error",
    "expected type",
    "expected value of type",
    "is not a valid",
    "must be",
)

# Transport status codes worth retrying (rate limit + transient upstream faults).
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

# Jittered exponential backoff parameters for the retry layer.
_MAX_ATTEMPTS = 5
_BACKOFF_BASE_SECONDS = 0.5
_BACKOFF_MAX_SECONDS = 20.0


class GnomadApiError(Exception):
    """Base exception for gnomAD API errors."""

    pass


class DataNotFoundError(GnomadApiError):
    """Raised when requested data is not found."""

    pass


class VariantNotFoundError(DataNotFoundError):
    """Raised when a variant is not found in the database."""

    pass


class UpstreamInputError(GnomadApiError):
    """Upstream rejected the request as malformed (deterministic, non-retryable)."""

    pass


class RateLimitedError(GnomadApiError):
    """Upstream rate-limited the request (HTTP 429) after retries (retryable)."""

    pass


def _is_retryable_transport_error(exc: BaseException) -> bool:
    """Whether a transport error is transient and worth retrying."""
    if isinstance(exc, TransportServerError):
        return exc.code in _RETRYABLE_STATUS
    return isinstance(exc, (TransportClosed, TimeoutError))


class BaseGnomadClient:
    """Base client for gnomAD GraphQL API."""

    def __init__(self, api_url: str | None = None, *, max_concurrency: int | None = None):
        """Initialize the API client.

        Args:
            api_url: Override the API URL from settings.
            max_concurrency: Override the in-flight request cap from settings.
        """
        self.api_url = api_url or settings.GNOMAD_API_URL
        self._transport = AIOHTTPTransport(
            url=self.api_url,
            timeout=settings.GNOMAD_REQUEST_TIMEOUT,
            ssl=True,
        )
        self._client = Client(
            transport=self._transport,
            fetch_schema_from_transport=False,
        )
        # Persistent reconnecting session, opened on first use. The client is
        # built by a sync factory so __init__ cannot await connect_async.
        self._session: Any = None
        self._connect_lock = asyncio.Lock()
        limit = settings.GNOMAD_MAX_CONCURRENCY if max_concurrency is None else max_concurrency
        self._semaphore = asyncio.Semaphore(max(1, limit))
        self.query_loader = QueryLoader()
        self.query_builder = QueryBuilder()

    async def _ensure_session(self) -> Any:
        """Open (once) and return the shared reconnecting session.

        Double-checked locking is required: the first concurrent burst must open
        the session exactly once, otherwise tasks race into multiple sessions or
        reintroduce TransportAlreadyConnected.
        """
        if self._session is None:
            async with self._connect_lock:
                if self._session is None:
                    self._session = await self._client.connect_async(reconnecting=True)
        return self._session

    async def _acquire_slot(self) -> None:
        """Acquire a concurrency slot, bounding the wait to give fast backpressure.

        An aggressive fan-out (e.g. 20 concurrent tool calls against a cap of 5)
        otherwise queues every excess request on the semaphore until the caller's
        OWN tool-call timeout fires, surfacing as an opaque timeout. Instead we
        wait at most GNOMAD_QUEUE_WAIT_TIMEOUT for a slot and then raise a
        retryable RateLimitedError, so the LLM gets actionable backpressure
        (retry with backoff) rather than a hang. The request timeout still covers
        only the upstream call, not this queue wait.
        """
        try:
            await asyncio.wait_for(
                self._semaphore.acquire(), timeout=settings.GNOMAD_QUEUE_WAIT_TIMEOUT
            )
        except TimeoutError as exc:
            raise RateLimitedError(
                "Local concurrency limit saturated "
                f"(max {settings.GNOMAD_MAX_CONCURRENCY} concurrent upstream requests). "
                "Retry with exponential backoff or fan out fewer calls at once."
            ) from exc

    async def _execute_with_retry(
        self, query_doc: Any, variables: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute one document with bounded concurrency + jittered retry.

        The semaphore is acquired per attempt (released during backoff sleep so
        other requests proceed). Only transient transport faults retry; GraphQL
        business errors (TransportQueryError) propagate immediately for the
        caller to classify. A saturated queue raises RateLimitedError, which is
        NOT retried here (fast backpressure) and propagates for classification.
        """
        delay = _BACKOFF_BASE_SECONDS
        for attempt in range(_MAX_ATTEMPTS):
            try:
                session = await self._ensure_session()
                await self._acquire_slot()
                try:
                    result: dict[str, Any] = await session.execute(
                        query_doc, variable_values=variables
                    )
                finally:
                    self._semaphore.release()
                return result
            except (TransportServerError, TransportClosed, TimeoutError) as exc:
                if not _is_retryable_transport_error(exc) or attempt == _MAX_ATTEMPTS - 1:
                    raise
                # Full jitter de-synchronizes a concurrent burst's retries; this is
                # backoff timing, not a security primitive.
                await asyncio.sleep(random.uniform(0, min(delay, _BACKOFF_MAX_SECONDS)))  # noqa: S311
                delay = min(delay * 2, _BACKOFF_MAX_SECONDS)
        raise GnomadApiError("retry loop exhausted")  # pragma: no cover - guard

    async def execute_query(
        self, query_name: str, variables: dict[str, Any], version: str = "v4"
    ) -> dict[str, Any]:
        """Execute a GraphQL query.

        Args:
            query_name: Name of the query to execute
            variables: Query variables
            version: API version

        Returns:
            Query result

        Raises:
            GnomadApiError: On API errors
            DataNotFoundError: When the requested entity is absent
            UpstreamInputError: When the upstream rejects the request as malformed
            RateLimitedError: When the upstream rate-limits after retries
        """
        try:
            query_string = self.query_loader.load_query(query_name, version)
            processed_vars = self.query_builder.process_variables(query_name, variables, version)

            result = await self._execute_doc(gql(query_string), processed_vars)

            # Check if data was found
            if query_name in result and result[query_name] is None:
                raise DataNotFoundError(
                    f"No data found for {query_name} with parameters: {processed_vars}"
                )

            return result

        except FileNotFoundError as e:
            raise GnomadApiError(f"Query not found: {e!s}") from e
        except Exception as e:
            if isinstance(e, GnomadApiError):
                raise
            raise GnomadApiError(f"Unexpected error: {e!s}") from e

    async def execute_raw_query(
        self, query_string: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute a caller-built GraphQL query string through the shared session.

        For DYNAMIC queries (e.g. an aliased ClinVar-submissions batch) that aren't
        loaded from a named .graphql file. Shares the persistent session, the
        concurrency semaphore, and the exponential-backoff retry of execute_query.
        """
        try:
            return await self._execute_doc(gql(query_string), variables or {})
        except Exception as e:
            if isinstance(e, GnomadApiError):
                raise
            raise GnomadApiError(f"Unexpected error: {e!s}") from e

    async def _execute_doc(self, query_doc: Any, variables: dict[str, Any]) -> dict[str, Any]:
        """Run a parsed document through the retry layer and classify faults.

        Shared by execute_query and execute_raw_query so the fault taxonomy (not
        found / invalid input / rate limited / upstream) lives in one place.
        """
        try:
            return await self._execute_with_retry(query_doc, variables)
        except TransportQueryError as e:
            if e.errors:
                error_msg = "; ".join([err.get("message", str(err)) for err in e.errors])
                lowered = error_msg.lower()
                # "not found" -> absent entity; deterministic validation phrasing ->
                # non-retryable input fault; everything else -> genuine server fault.
                if any("not found" in err.get("message", "").lower() for err in e.errors):
                    raise DataNotFoundError(error_msg) from e
                if any(signal in lowered for signal in _INPUT_ERROR_SIGNALS):
                    raise UpstreamInputError(error_msg) from e
                raise GnomadApiError(f"GraphQL error: {error_msg}") from e
            raise GnomadApiError(f"Query error: {e!s}") from e
        except TransportServerError as e:
            # A 429 that survived the retry layer is a persistent rate limit.
            if e.code == 429:
                raise RateLimitedError(f"Rate limited by upstream API (HTTP 429): {e!s}") from e
            raise GnomadApiError(f"API request failed: {e!s}") from e
        except TransportError as e:
            raise GnomadApiError(f"API request failed: {e!s}") from e

    async def close(self) -> None:
        """Close the client connection (idempotent)."""
        if self._session is not None:
            self._session = None
            try:
                await self._client.close_async()
            except Exception:  # best-effort, idempotent teardown
                logger.debug("close_async raised during teardown", exc_info=True)
        else:
            await self._transport.close()

    async def __aenter__(self) -> "BaseGnomadClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
