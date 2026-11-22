"""Base GraphQL client with centralized query management.

Concurrency model: one persistent reconnecting gql session per client, opened
lazily under a double-checked lock and reused across all concurrent tasks. The
one-shot ``Client.execute_async`` connects AND closes the shared transport on
every call, so two concurrent calls race into ``TransportAlreadyConnected``; a
single connected aiohttp session is safe for concurrent ``execute`` and gives
true HTTP parallelism. A token bucket paces the request RATE (the upstream
limit is per IP per minute), an ``asyncio.Semaphore`` bounds in-flight requests,
and a jittered retry layer with a shared 429 cooldown absorbs residual 429s and
transient transport faults.
"""

import asyncio
import logging
import math
import random
import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
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
# Upper bound on an honoured upstream Retry-After, so one header cannot park a
# tool call past the caller's own timeout.
_RETRY_AFTER_CAP_SECONDS = 30.0


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
    """Upstream rate-limited the request (HTTP 429) after retries (retryable).

    ``retry_after_seconds`` is the whole-second wait surfaced to the caller; it
    defaults to the 429 cooldown when the raise site has no better estimate.
    """

    def __init__(self, message: str, *, retry_after_seconds: float | None = None):
        super().__init__(message)
        if retry_after_seconds is None:
            retry_after_seconds = settings.GNOMAD_RATE_LIMIT_COOLDOWN
        self.retry_after_seconds = max(1, math.ceil(retry_after_seconds))


def _is_retryable_transport_error(exc: BaseException) -> bool:
    """Whether a transport error is transient and worth retrying.

    A timeout is not: it already took GNOMAD_REQUEST_TIMEOUT, and a second one
    would outlast the caller's own tool-call timeout.
    """
    if isinstance(exc, TransportServerError):
        return exc.code in _RETRYABLE_STATUS
    return isinstance(exc, TransportClosed)


def _retry_after_seconds(exc: BaseException) -> float | None:
    """Capped upstream Retry-After (delta-seconds) from a gql transport error.

    gql chains the aiohttp ClientResponseError (which carries the response
    headers) as ``__cause__``. ponytail: the HTTP-date form is ignored and falls
    back to jittered backoff; parse it if the Broad API ever sends one.
    """
    headers = getattr(exc.__cause__, "headers", None)
    value = headers.get("Retry-After") if headers else None
    try:
        return min(max(int(value), 0), _RETRY_AFTER_CAP_SECONDS) if value else None
    except ValueError:
        return None


def _rate_limit_headers(exc: BaseException) -> dict[str, str]:
    """Rate-related response headers of a 429, for operator logs only.

    Header values come from the upstream or its load balancer, never from the
    caller; the response BODY is deliberately not read (see _execute_doc).
    """
    headers = getattr(exc.__cause__, "headers", None) or {}
    return {
        str(name): str(value)[:100]
        for name, value in headers.items()
        if "ratelimit" in name.lower().replace("-", "") or name.lower() == "retry-after"
    }


# Loop time by which the current tool call must stop WAITING on upstream (pacing,
# cooldown, retry backoff), in a one-item list so each request can push it back by
# the time it spent inside upstream; None outside a tool call (per-request budget).
_CALL_DEADLINE: ContextVar[list[float] | None] = ContextVar("gnomad_call_deadline", default=None)


async def with_call_budget[T](call: Callable[[], Awaitable[T]]) -> T:
    """Run one tool call under a single GNOMAD_CALL_WAIT_BUDGET shared by all its requests."""
    deadline = asyncio.get_running_loop().time() + settings.GNOMAD_CALL_WAIT_BUDGET
    token = _CALL_DEADLINE.set([deadline])
    try:
        return await call()
    finally:
        _CALL_DEADLINE.reset(token)


# Queue-wait budget override for best-effort requests (see without_waiting).
_QUEUE_WAIT: ContextVar[float | None] = ContextVar("gnomad_queue_wait", default=None)


async def without_waiting[T](call: Callable[[], Awaitable[T]]) -> T:
    """Run best-effort requests that raise RateLimitedError rather than wait for a rate token."""
    token = _QUEUE_WAIT.set(0.0)
    try:
        return await call()
    finally:
        _QUEUE_WAIT.reset(token)


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
            client_session_args={"trust_env": True},
        )
        self._client = Client(
            transport=self._transport,
            fetch_schema_from_transport=False,
            # gql wraps every execute in its own 10 s timeout unless told otherwise.
            execute_timeout=settings.GNOMAD_REQUEST_TIMEOUT,
        )
        # Persistent reconnecting session, opened on first use. The client is
        # built by a sync factory so __init__ cannot await connect_async.
        self._session: Any = None
        # Loop time before which no request may hit upstream (shared Retry-After).
        self._cooldown_until = 0.0
        # Token bucket (GCRA): one request per interval after a burst. The limit
        # is per egress IP, so the state is shared by every request.
        rpm = settings.GNOMAD_MAX_REQUESTS_PER_MINUTE
        self._rate_interval = 60.0 / rpm if rpm > 0 else 0.0
        self._rate_burst_tolerance = self._rate_interval * (max(1, settings.GNOMAD_RATE_BURST) - 1)
        self._rate_tat = 0.0  # loop time at which the bucket is full again
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
                    # retry_execute=False: _execute_with_retry is the ONLY retry
                    # layer. gql's default inner 5-try retry nested inside ours
                    # (25 POSTs per call on a persistent 429) while holding the
                    # concurrency slot and ignoring Retry-After.
                    self._session = await self._client.connect_async(
                        reconnecting=True, retry_execute=False
                    )
        return self._session

    async def _acquire_slot(self, *, timeout: float | None = None) -> None:
        """Acquire a concurrency slot, bounding the wait to give fast backpressure.

        An aggressive fan-out (e.g. 20 concurrent tool calls against a cap of 5)
        otherwise queues every excess request on the semaphore until the caller's
        OWN tool-call timeout fires, surfacing as an opaque timeout. The retry
        layer passes a per-call remaining budget so all attempts share one
        GNOMAD_QUEUE_WAIT_TIMEOUT window for slot waits, then raise a retryable
        RateLimitedError. The request timeout still covers only the upstream
        call, not this queue wait.
        """
        wait_timeout = settings.GNOMAD_QUEUE_WAIT_TIMEOUT if timeout is None else timeout
        if not self._semaphore.locked():  # wait_for(timeout=0) refuses even a free slot
            await self._semaphore.acquire()
            return
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=max(0.0, wait_timeout))
        except TimeoutError as exc:
            raise RateLimitedError(
                "Local concurrency limit saturated "
                f"(max {settings.GNOMAD_MAX_CONCURRENCY} concurrent upstream requests). "
                "Retry with exponential backoff or fan out fewer calls at once."
            ) from exc

    def _reserve_send_time(
        self, now: float, queue_wait_deadline: float, call_deadline: float = math.inf
    ) -> tuple[float, float]:
        """Take a rate token; return (seconds to wait, cooldown part of that wait).

        GNOMAD_RATE_BURST requests go out immediately, then one per
        60/GNOMAD_MAX_REQUESTS_PER_MINUTE seconds. A shared 429 cooldown holds
        every request back and is NOT charged to the queue-wait budget (upstream
        imposed it); a pacing wait that would overrun the budget raises a
        retryable RateLimitedError without taking a token (fast backpressure).
        So does any wait, cooldown included, that would pass the call's budget.
        """
        cooldown = max(0.0, self._cooldown_until - now)
        send_at = max(now + cooldown, self._rate_tat - self._rate_burst_tolerance)
        if send_at > call_deadline:
            raise RateLimitedError(
                "gnomAD is rate-limiting and the next send time is beyond this call's wait "
                f"budget ({settings.GNOMAD_CALL_WAIT_BUDGET} s). Retry after retry_after_seconds.",
                retry_after_seconds=send_at - now,
            )
        if send_at > queue_wait_deadline + cooldown:
            raise RateLimitedError(
                "Local request-rate limit saturated "
                f"(max {settings.GNOMAD_MAX_REQUESTS_PER_MINUTE} upstream requests per minute). "
                "Retry after retry_after_seconds or fan out fewer calls at once.",
                retry_after_seconds=send_at - now,
            )
        self._rate_tat = max(self._rate_tat, send_at) + self._rate_interval
        return send_at - now, cooldown

    async def _wait_for_send_time(
        self, loop: asyncio.AbstractEventLoop, queue_wait_deadline: float, call_deadline: float
    ) -> tuple[float, float]:
        """Wait out pacing and any 429 cooldown; return (queue-wait deadline, time waited to).

        A 429 that arrives while this request waits voids its send time: the
        cooldown is re-checked after the pause and the request reserves again, so
        nothing that was already queued goes out during a cooldown.
        """
        while True:
            now = loop.time()
            pause, cooldown = self._reserve_send_time(now, queue_wait_deadline, call_deadline)
            queue_wait_deadline += cooldown
            if pause <= 0:
                return queue_wait_deadline, now
            try:
                await asyncio.sleep(pause)
            except asyncio.CancelledError:
                self._rate_tat -= self._rate_interval  # a cancelled waiter gives its token back
                raise
            if now + pause >= self._cooldown_until:
                return queue_wait_deadline, now + pause

    async def _execute_with_retry(
        self, query_doc: Any, variables: dict[str, Any], name: str = "raw"
    ) -> dict[str, Any]:
        """Execute one document with paced, bounded concurrency + jittered retry.

        A rate token and the semaphore are taken per attempt (the slot is
        released during backoff sleep so other requests proceed). Only transient
        transport faults retry; GraphQL business errors (TransportQueryError)
        propagate immediately for the caller to classify. A saturated queue
        raises RateLimitedError, which is NOT retried here (fast backpressure)
        and propagates for classification, unless an earlier attempt failed
        upstream: then that fault is raised so a 5xx stays upstream_unavailable.
        Both budgets count waiting only; time inside a request pushes them back.
        """
        delay = _BACKOFF_BASE_SECONDS
        loop = asyncio.get_running_loop()
        started_at = loop.time()
        queue_wait = _QUEUE_WAIT.get()
        if queue_wait is None:
            queue_wait = settings.GNOMAD_QUEUE_WAIT_TIMEOUT
        queue_wait_deadline = started_at + queue_wait
        # One budget for every wait of the tool call (all its requests and retries).
        call_deadline = _CALL_DEADLINE.get() or [started_at + settings.GNOMAD_CALL_WAIT_BUDGET]
        last_fault: BaseException | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                session = await self._ensure_session()
                try:
                    # Pacing plus any shared 429 cooldown: the limit is per egress
                    # IP, not per request.
                    queue_wait_deadline, now = await self._wait_for_send_time(
                        loop, queue_wait_deadline, call_deadline[0]
                    )
                    wait_left = max(0.0, min(queue_wait_deadline, call_deadline[0]) - now)
                    await self._acquire_slot(timeout=wait_left)
                except RateLimitedError as exc:
                    if last_fault is None or getattr(last_fault, "code", None) == 429:
                        raise exc from last_fault
                    raise last_fault from exc
                sent_at = loop.time()
                started = time.perf_counter()
                outcome: int | str = "ok"
                try:
                    result: dict[str, Any] = await session.execute(
                        query_doc, variable_values=variables
                    )
                except BaseException as exc:
                    outcome = getattr(exc, "code", None) or type(exc).__name__
                    raise
                finally:
                    self._semaphore.release()
                    in_request = loop.time() - sent_at
                    queue_wait_deadline += in_request
                    call_deadline[0] += in_request
                    # Query NAME only: variables and bodies can carry caller text.
                    logger.info(
                        "gnomad_upstream_request query=%s outcome=%s attempt=%d duration_ms=%d",
                        name,
                        outcome,
                        attempt + 1,
                        (time.perf_counter() - started) * 1000,
                    )
                return result
            except (TransportServerError, TransportClosed, TimeoutError) as exc:
                last_fault = exc
                retry_after = _retry_after_seconds(exc)
                if getattr(exc, "code", None) == 429:
                    logger.warning(
                        "gnomad_upstream_429 query=%s attempt=%d rate_headers=%s",
                        name,
                        attempt + 1,
                        _rate_limit_headers(exc),
                    )
                    if retry_after is None:
                        retry_after = float(settings.GNOMAD_RATE_LIMIT_COOLDOWN)
                if retry_after is not None:
                    # Stop the whole process sending until the window reopens,
                    # then resume at the steady pace (bucket emptied: no burst).
                    self._cooldown_until = max(self._cooldown_until, loop.time() + retry_after)
                    self._rate_tat = max(
                        self._rate_tat, self._cooldown_until + self._rate_burst_tolerance
                    )
                if not _is_retryable_transport_error(exc) or attempt == _MAX_ATTEMPTS - 1:
                    raise
                # Full jitter de-synchronizes a concurrent burst's retries; this is
                # backoff timing, not a security primitive.
                wait = random.uniform(0, min(delay, _BACKOFF_MAX_SECONDS))  # noqa: S311
                if retry_after is not None:
                    wait = max(wait, retry_after)
                    # An upstream-imposed wait is not local queueing: keep the
                    # queue-wait budget so the retry can outlast the cooldown.
                    queue_wait_deadline += wait
                if loop.time() + wait > call_deadline[0]:
                    raise  # the next wait would pass the call's budget: answer now
                await asyncio.sleep(wait)
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

            result = await self._execute_doc(gql(query_string), processed_vars, query_name)

            # Check if data was found
            if query_name in result and result[query_name] is None:
                raise DataNotFoundError(
                    f"No data found for {query_name} with parameters: {processed_vars}"
                )

            return result

        except FileNotFoundError as e:
            # Fixed message: the missing file path is an internal detail and str(e)
            # is never surfaced to the caller.
            raise GnomadApiError("The requested gnomAD query is not available.") from e
        except Exception as e:
            if isinstance(e, GnomadApiError):
                raise
            # Body-free: str(e) of an unexpected fault can embed upstream/parse
            # detail; the original stays chained (``from e``) for operator logs.
            raise GnomadApiError(
                "An unexpected error occurred while querying the gnomAD GraphQL API."
            ) from e

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
            # Body-free: str(e) of an unexpected fault can embed upstream/parse
            # detail; the original stays chained (``from e``) for operator logs.
            raise GnomadApiError(
                "An unexpected error occurred while querying the gnomAD GraphQL API."
            ) from e

    async def _execute_doc(
        self, query_doc: Any, variables: dict[str, Any], name: str = "raw"
    ) -> dict[str, Any]:
        """Run a parsed document through the retry layer and classify faults.

        Shared by execute_query and execute_raw_query so the fault taxonomy (not
        found / invalid input / rate limited / upstream) lives in one place.
        """
        try:
            return await self._execute_with_retry(query_doc, variables, name)
        except TransportQueryError as e:
            if e.errors:
                # The upstream ``errors[].message`` values are inspected ONLY to
                # classify the fault; their TEXT is NEVER interpolated into the
                # caller-visible exception. A caller-influenced query can make
                # gnomAD reflect hostile prose and control/zero-width/bidi/NUL
                # code points into ``errors[].message``, so echoing that body
                # would smuggle attacker-controlled text into a caller-visible
                # error message. Fixed, body-free messages are raised instead
                # (the error COUNT is a bounded, non-attacker-controlled scalar);
                # the raw upstream text is deliberately neither surfaced nor
                # logged, preserving the no-PII-in-logs invariant.
                count = len(e.errors)
                messages = [str(err.get("message", "")).lower() for err in e.errors]
                # "not found" -> absent entity; deterministic validation phrasing ->
                # non-retryable input fault; everything else -> genuine server fault.
                if any("not found" in msg for msg in messages):
                    raise DataNotFoundError(
                        f"The gnomAD GraphQL API reported the record as not found "
                        f"({count} error(s))."
                    ) from e
                if any(signal in msg for msg in messages for signal in _INPUT_ERROR_SIGNALS):
                    raise UpstreamInputError(
                        f"The gnomAD GraphQL API rejected the request as invalid "
                        f"({count} error(s))."
                    ) from e
                raise GnomadApiError(
                    f"The gnomAD GraphQL API returned an error ({count} error(s))."
                ) from e
            raise GnomadApiError("The gnomAD GraphQL API returned a query error.") from e
        except TransportServerError as e:
            # NEVER interpolate str(e): for a malformed / non-GraphQL upstream
            # response the gql aiohttp transport embeds the raw response.text in
            # the exception message, which a caller-influenced query could fill
            # with hostile prose + control code points. Raise a fixed, body-free
            # message keyed on the HTTP status (a bounded, non-attacker-controlled
            # scalar). The original exception stays chained (``from e``) for
            # operator tracebacks; it is never surfaced to the caller.
            if e.code == 429:
                # A 429 that survived the retry layer is a persistent rate limit.
                raise RateLimitedError(
                    "The gnomAD GraphQL API rate-limited the request (HTTP 429).",
                    retry_after_seconds=self._cooldown_until - asyncio.get_running_loop().time(),
                ) from e
            raise GnomadApiError(
                f"The gnomAD GraphQL API returned a server error (HTTP {e.code})."
            ) from e
        except TimeoutError as e:
            raise GnomadApiError(
                "The gnomAD GraphQL API did not answer within "
                f"{settings.GNOMAD_REQUEST_TIMEOUT} s. Retry later."
            ) from e
        except TransportError as e:
            # Covers TransportProtocolError (whose message embeds the raw
            # response.text for a non-GraphQL body), TransportClosed, and generic
            # transport faults. Body-free fixed message; str(e) is never echoed.
            raise GnomadApiError(
                "The gnomAD GraphQL API was unreachable or returned a malformed response."
            ) from e

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

    async def __aenter__(self) -> BaseGnomadClient:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
