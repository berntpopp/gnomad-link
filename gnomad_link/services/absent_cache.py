"""Short-TTL memory of empty or not-found answers in front of an alru-cached lookup.

An absent answer is kept only ``NEGATIVE_TTL_SECONDS`` (not the positive TTL): it
may stem from a transient upstream fault, yet a repeat within the window still
spends no upstream request against the shared per-IP rate budget.
"""

import time
from typing import Any

from gnomad_link.api.base_client import DataNotFoundError

NEGATIVE_TTL_SECONDS = 300.0


class AbsentCache:
    """(lookup, *args) -> (expiry, empty answer or not-found error)."""

    def __init__(self, maxsize: int) -> None:
        self._entries: dict[tuple[Any, ...], tuple[float, Any]] = {}
        self._maxsize = maxsize

    async def call(self, cached: Any, *args: Any) -> Any:
        """Await ``cached(*args)``; replay a recent empty or not-found answer instead."""
        key = (cached, *args)
        expiry, answer = self._entries.get(key, (0.0, None))
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
            self._entries[key] = (time.monotonic() + NEGATIVE_TTL_SECONDS, answer)
        if isinstance(answer, DataNotFoundError):
            raise type(answer)(*answer.args)  # a fresh error: replays must not grow one traceback
        return answer

    def clear(self) -> None:
        self._entries.clear()
