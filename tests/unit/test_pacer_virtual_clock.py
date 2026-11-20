"""The upstream pacer under contention, on a virtual clock (no network, no real waits)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from gql.transport.exceptions import TransportServerError

from gnomad_link.api import RateLimitedError, with_call_budget
from gnomad_link.api.base_client import BaseGnomadClient
from gnomad_link.config import settings

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
