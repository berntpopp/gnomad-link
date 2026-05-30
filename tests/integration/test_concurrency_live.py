"""Live concurrency check for the shared gql client. Gated by `integration`.

Regression for M-3: a single shared AIOHTTPTransport with one-shot execute_async
raced into "Transport is already connected" under concurrent calls and tripped
gnomAD's rate limiter. The persistent reconnecting session + bounded semaphore +
jittered retry must let a concurrent burst complete cleanly.
"""

from __future__ import annotations

import asyncio

import pytest

from gnomad_link.api.client import UnifiedGnomadClient

pytestmark = pytest.mark.integration

# Known-present variants (PCSK9 splice; CFTR F508del), repeated to force a
# concurrent burst on the shared client.
_VARIANTS = ["1-55051215-G-GA", "7-117559590-ATCT-A"] * 6


@pytest.mark.asyncio
async def test_concurrent_variant_queries_do_not_race_or_storm() -> None:
    client = UnifiedGnomadClient()
    try:
        results = await asyncio.gather(
            *(client.get_variant(vid, "gnomad_r4") for vid in _VARIANTS),
            return_exceptions=True,
        )
    finally:
        await client.close()

    # The M-3 invariant: a concurrent burst must NOT race into
    # "Transport is already connected", and the semaphore + jittered retry must
    # absorb any transient 429s so every known-present variant resolves to data.
    for vid, result in zip(_VARIANTS, results, strict=True):
        assert not isinstance(result, BaseException), f"{vid} failed: {result!r}"
        assert isinstance(result, dict)
        assert result.get("variant") is not None, vid
