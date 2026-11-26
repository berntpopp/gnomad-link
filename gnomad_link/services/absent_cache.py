"""Short-TTL memory of empty or not-found answers in front of an alru-cached lookup.

An absent answer is kept only ``NEGATIVE_TTL_SECONDS`` (not the positive TTL): it
may stem from a transient upstream fault, yet a repeat within the window still
spends no upstream request against the shared per-IP rate budget.
"""

import time
from collections.abc import Awaitable, Callable
from typing import Any

from async_lru import alru_cache

from gnomad_link.api.base_client import DataNotFoundError, note_fetch, with_fetch_times

NEGATIVE_TTL_SECONDS = 300.0


class FetchTimeCache:
    """An ``alru_cache`` whose hits replay the upstream fetch time that filled the entry.

    Response-Envelope Standard v1.2: a cached result keeps its original ``retrieved_at``.
    """

    def __init__(self, impl: Callable[..., Awaitable[Any]], maxsize: int, ttl: float) -> None:
        async def stamped(*args: Any) -> tuple[Any, float]:
            value, times = await with_fetch_times(lambda: impl(*args))
            return value, min(times, default=time.time())

        self._cached = alru_cache(maxsize=maxsize, ttl=ttl)(stamped)
        self.cache_invalidate = self._cached.cache_invalidate
        self.cache_clear = self._cached.cache_clear
        self.cache_info = self._cached.cache_info

    async def __call__(self, *args: Any) -> Any:
        value, fetched_at = await self._cached(*args)
        note_fetch(fetched_at)
        return value


class AbsentCache:
    """(lookup, *args) -> (expiry, empty answer or not-found error, upstream fetch time)."""

    def __init__(self, maxsize: int) -> None:
        self._entries: dict[tuple[Any, ...], tuple[float, Any, float]] = {}
        self._maxsize = maxsize

    async def call(self, cached: Any, *args: Any) -> Any:
        """Await ``cached(*args)``; replay a recent empty or not-found answer instead."""
        key = (cached, *args)
        expiry, answer, fetched_at = self._entries.get(key, (0.0, None, 0.0))
        if expiry <= time.monotonic():
            try:
                answer = await cached(*args)
            except DataNotFoundError as exc:
                answer = exc
            else:
                if answer:
                    return answer
                cached.cache_invalidate(*args)  # an empty answer must not get the positive TTL
            if len(self._entries) >= self._maxsize:
                self._entries.clear()  # ponytail: wholesale reset; use an LRU if it ever churns
            # ponytail: the replay is dated to its arrival, not to the request's send time
            self._entries[key] = (time.monotonic() + NEGATIVE_TTL_SECONDS, answer, time.time())
        else:
            note_fetch(fetched_at)  # a replay keeps the time of the fetch that stored it
        if isinstance(answer, DataNotFoundError):
            raise type(answer)(*answer.args)  # a fresh error: replays must not grow one traceback
        return answer

    def clear(self) -> None:
        self._entries.clear()
