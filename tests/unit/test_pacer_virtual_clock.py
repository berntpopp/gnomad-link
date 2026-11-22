"""The upstream pacer under contention, on a virtual clock (no network, no real waits)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from gql.transport.exceptions import TransportServerError

from gnomad_link.api import RateLimitedError, with_call_budget, without_waiting
from gnomad_link.api.base_client import BaseGnomadClient, GnomadApiError
from gnomad_link.config import settings
from gnomad_link.mcp.errors import McpErrorContext, _classify

T0 = 1000.0


class _VirtualLoop(asyncio.SelectorEventLoop):
    """Event loop whose clock jumps to the next timer when nothing is ready."""

    _now = T0

    def time(self) -> float:
        return self._now

    def _run_once(self) -> None:
        if not self._ready and self._scheduled:  # type: ignore[attr-defined]
            due = [h._when for h in self._scheduled if not h._cancelled]  # type: ignore[attr-defined]
            if due:
                self._now = max(self._now, min(due))
        super()._run_once()  # type: ignore[misc]


class _RetryAfterError(Exception):
    def __init__(self, retry_after: int) -> None:
        self.headers = {"Retry-After": str(retry_after)}


class _Session:
    """Upstream stand-in: refuses with 429 while ``refuse(seconds since start)`` is true."""

    def __init__(self, refuse: Callable[[float], bool], retry_after: int | None = None) -> None:
        self.refuse, self.retry_after = refuse, retry_after
        self.sent: list[float] = []
        self.refused: list[float] = []

    async def execute(self, _doc: Any, variable_values: Any = None) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        self.sent.append(round(loop.time() - T0, 2))
        await asyncio.sleep(0.1)
        if self.refuse(loop.time() - T0):
            self.refused.append(round(loop.time() - T0, 2))
            error = TransportServerError("x", 429)
            if self.retry_after is not None:
                error.__cause__ = _RetryAfterError(self.retry_after)
            raise error
        return {"ok": True}


def _run(scenario: Callable[[], Coroutine[Any, Any, None]]) -> None:
    loop = _VirtualLoop()
    try:
        loop.run_until_complete(scenario())
    finally:
        loop.close()


@pytest.fixture(autouse=True)
def _defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GNOMAD_MAX_REQUESTS_PER_MINUTE", 20)
    monkeypatch.setattr(settings, "GNOMAD_RATE_BURST", 5)
    monkeypatch.setattr(settings, "GNOMAD_RATE_LIMIT_COOLDOWN", 15)
    monkeypatch.setattr(settings, "GNOMAD_QUEUE_WAIT_TIMEOUT", 20)
    monkeypatch.setattr(settings, "GNOMAD_CALL_WAIT_BUDGET", 40)


def _client(session: _Session) -> BaseGnomadClient:
    client = BaseGnomadClient(api_url="https://test.invalid/graphql")
    client._session = session
    return client


async def _timed(client: BaseGnomadClient) -> tuple[str, float, int | None]:
    loop = asyncio.get_running_loop()
    started = loop.time()
    try:
        await client._execute_doc(None, {}, "q")
    except RateLimitedError as exc:
        return "rate_limited", loop.time() - started, exc.retry_after_seconds
    return "ok", loop.time() - started, None


@pytest.mark.parametrize("retry_after", [None, 30])
def test_persistent_429_answers_within_the_call_budget(retry_after: int | None) -> None:
    async def scenario() -> None:
        client = _client(_Session(lambda _t: True, retry_after))
        outcome, elapsed, hint = await _timed(client)
        assert outcome == "rate_limited"
        assert elapsed <= settings.GNOMAD_CALL_WAIT_BUDGET + 1  # was 60 s / 120 s
        assert hint is not None and 1 <= hint <= 30

    _run(scenario)


def test_one_budget_covers_every_request_of_a_tool_call() -> None:
    async def scenario() -> None:
        client = _client(_Session(lambda _t: True))
        loop = asyncio.get_running_loop()

        async def tool_call() -> list[str]:
            # e.g. the primary lookup, then the other-build lookup
            return [(await _timed(client))[0], (await _timed(client))[0]]

        started = loop.time()
        assert await with_call_budget(tool_call) == ["rate_limited", "rate_limited"]
        assert loop.time() - started <= settings.GNOMAD_CALL_WAIT_BUDGET + 1

    _run(scenario)


def test_requests_already_queued_do_not_go_out_during_a_cooldown() -> None:
    async def scenario() -> None:
        session = _Session(lambda t: t < 40)  # upstream refuses for the first 40 s
        client = _client(session)
        outcomes = await asyncio.gather(*(_timed(client) for _ in range(11)))

        cooldown = settings.GNOMAD_RATE_LIMIT_COOLDOWN
        for refused_at in session.refused:
            in_cooldown = [s for s in session.sent if refused_at < s < refused_at + cooldown]
            assert in_cooldown == [], (refused_at, session.sent)
        # The 5-request burst is refused once; after that one probe per cooldown.
        assert len(session.sent) <= 5 + 2 + 11
        assert all(elapsed <= 41 for _, elapsed, _ in outcomes)
        assert {o for o, _, _ in outcomes} <= {"ok", "rate_limited"}

    _run(scenario)


def test_a_cancelled_waiter_gives_its_send_slot_back() -> None:
    async def scenario() -> None:
        session = _Session(lambda _t: False)
        client = _client(session)
        tasks = [asyncio.ensure_future(_timed(client)) for _ in range(11)]
        await asyncio.sleep(0.5)  # 5 sent, 6 hold a token and wait
        for task in tasks[5:]:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        outcome, elapsed, _ = await _timed(client)
        assert outcome == "ok"
        assert elapsed <= 3.0  # the next free slot, not behind six abandoned ones (20 s)
        assert len(session.sent) == 6

    _run(scenario)


class _SlowSession:
    """Upstream stand-in: every request takes ``seconds``, then ``fail`` decides its fate."""

    def __init__(self, seconds: float, fail: Callable[[int], BaseException | None]) -> None:
        self.seconds, self.fail, self.calls = seconds, fail, 0

    async def execute(self, _doc: Any, variable_values: Any = None) -> dict[str, Any]:
        self.calls += 1
        await asyncio.sleep(self.seconds)
        error = self.fail(self.calls)
        if error is not None:
            raise error
        return {"ok": True}


def test_execute_timeout_is_the_configured_request_timeout() -> None:
    client = BaseGnomadClient(api_url="https://test.invalid/graphql")
    assert client._client.execute_timeout == settings.GNOMAD_REQUEST_TIMEOUT  # gql default is 10


def test_hanging_upstream_is_upstream_unavailable_not_rate_limited() -> None:
    """#154: two 10 s timeouts used to spend the 20 s queue budget and read as rate_limited."""

    async def scenario() -> None:
        session = _SlowSession(10, lambda _n: TimeoutError())
        client = _client(session)  # type: ignore[arg-type]
        with pytest.raises(GnomadApiError) as info:
            await with_call_budget(lambda: client._execute_doc(None, {}, "q"))
        assert not isinstance(info.value, RateLimitedError)
        assert isinstance(info.value.__cause__, TimeoutError)
        code, retryable, _, _ = _classify(info.value, McpErrorContext(tool_name="t"))
        assert (code, retryable) == ("upstream_unavailable", True)
        assert session.calls == 1  # a timed-out request is not retried (60 s each)

    _run(scenario)


def test_slow_5xx_retries_are_not_charged_to_the_queue_wait_budget() -> None:
    async def scenario() -> None:
        session = _SlowSession(15, lambda n: TransportServerError("x", 503) if n < 3 else None)
        client = _client(session)  # type: ignore[arg-type]
        assert await client._execute_doc(None, {}, "q") == {"ok": True}
        assert session.calls == 3

    _run(scenario)


def test_time_inside_requests_is_not_charged_to_the_call_budget() -> None:
    async def scenario() -> None:
        client = _client(_SlowSession(9, lambda _n: None))  # type: ignore[arg-type]

        async def tool_call() -> int:
            for _ in range(6):  # 54 s of upstream work, no waiting
                await client._execute_doc(None, {}, "q")
            return 6

        assert await with_call_budget(tool_call) == 6

    _run(scenario)


def test_budget_exhausted_after_a_5xx_reraises_the_5xx() -> None:
    async def scenario() -> None:
        client = _client(_SlowSession(0.1, lambda _n: TransportServerError("x", 503)))  # type: ignore[arg-type]
        real = client._reserve_send_time
        calls = 0

        def reserve(*args: Any) -> tuple[float, float]:
            nonlocal calls
            calls += 1
            if calls > 1:
                raise RateLimitedError("Local request-rate limit saturated")
            return real(*args)

        client._reserve_send_time = reserve  # type: ignore[method-assign]
        with pytest.raises(GnomadApiError) as info:
            await client._execute_doc(None, {}, "q")
        assert not isinstance(info.value, RateLimitedError)
        assert isinstance(info.value.__cause__, TransportServerError)

    _run(scenario)


def test_budget_exhausted_after_a_429_is_rate_limited_and_chained() -> None:
    async def scenario() -> None:
        client = _client(_SlowSession(0.1, lambda _n: TransportServerError("x", 429)))  # type: ignore[arg-type]
        with pytest.raises(RateLimitedError) as info:
            await client._execute_doc(None, {}, "q")
        assert isinstance(info.value.__cause__, TransportServerError)

    _run(scenario)


def test_without_waiting_gives_up_instead_of_spending_a_paced_token() -> None:
    """#155: best-effort enrichment never queues for a rate token."""

    async def scenario() -> None:
        session = _Session(lambda _t: False)
        client = _client(session)
        for _ in range(settings.GNOMAD_RATE_BURST):  # a free token is used without waiting
            await without_waiting(lambda: client._execute_doc(None, {}, "q"))
        loop = asyncio.get_running_loop()
        started = loop.time()
        with pytest.raises(RateLimitedError):
            await without_waiting(lambda: client._execute_doc(None, {}, "q"))
        assert loop.time() - started < 0.5
        assert len(session.sent) == settings.GNOMAD_RATE_BURST
        assert (await _timed(client))[0] == "ok"  # its token was not taken

    _run(scenario)
