"""Batched ClinVar submissions fetch: replaces the one-call-per-variant storm.

gnomAD enforces a query-cost limit of 25, so batches are chunked at 24 (the
reference's BATCH_SIZE of 50 would fail every batch). These tests pin the chunk
size and the aliased-query builder without any network access.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import pytest

from gnomad_link.api.client import (
    _CLINVAR_SUBMISSIONS_BATCH_SIZE,
    UnifiedGnomadClient,
    _build_clinvar_submissions_query,
)


def test_batch_size_within_gnomad_cost_limit() -> None:
    # gnomAD's max allowed query cost is 25 (one unit per clinvar_variant alias).
    assert _CLINVAR_SUBMISSIONS_BATCH_SIZE <= 25


def test_build_query_aliases_each_variant_with_enum_genome() -> None:
    q = _build_clinvar_submissions_query(["1-2-A-G", "7-9-C-T"], "GRCh38")
    assert 'v0: clinvar_variant(variant_id: "1-2-A-G", reference_genome: GRCh38)' in q
    assert 'v1: clinvar_variant(variant_id: "7-9-C-T", reference_genome: GRCh38)' in q
    assert "submissions { clinical_significance }" in q
    # reference_genome is a GraphQL enum (unquoted), not a string literal.
    assert 'reference_genome: "GRCh38"' not in q


@pytest.mark.asyncio
async def test_submissions_batch_chunks_by_24(monkeypatch: pytest.MonkeyPatch) -> None:
    client = UnifiedGnomadClient()
    chunk_sizes: list[int] = []

    async def fake_raw(
        query_string: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        ids = re.findall(r'variant_id: "([^"]+)"', query_string)
        chunk_sizes.append(len(ids))
        return {
            f"v{i}": {"variant_id": vid, "submissions": [{"clinical_significance": "Pathogenic"}]}
            for i, vid in enumerate(ids)
        }

    monkeypatch.setattr(client, "execute_raw_query", fake_raw)
    ids = [f"1-{i}-A-G" for i in range(50)]
    result = await client.get_clinvar_submissions_batch(ids, "GRCh38")
    await client.close()

    assert len(result) == 50
    # 50 ids -> ceil(50/24) = 3 chunks of [24, 24, 2] (NOT 50 per-variant calls).
    assert sorted(chunk_sizes, reverse=True) == [24, 24, 2]
    assert result["1-0-A-G"] == [{"clinical_significance": "Pathogenic"}]


@pytest.mark.asyncio
async def test_submissions_batch_empty_input_makes_no_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = UnifiedGnomadClient()
    called = False

    async def fake_raw(
        query_string: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(client, "execute_raw_query", fake_raw)
    result = await client.get_clinvar_submissions_batch([], "GRCh38")
    await client.close()

    assert result == {}
    assert called is False


@pytest.mark.asyncio
async def test_submissions_batch_failed_chunk_is_best_effort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = UnifiedGnomadClient()

    async def fake_raw(
        query_string: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        raise RuntimeError("upstream blew up")

    monkeypatch.setattr(client, "execute_raw_query", fake_raw)
    result = await client.get_clinvar_submissions_batch(["1-1-A-G"], "GRCh38")
    await client.close()

    # A failed batch contributes nothing rather than failing the whole resolution.
    assert result == {}
    assert result.failed_chunks == 1
    assert result.failed_variant_ids == ["1-1-A-G"]


@pytest.mark.asyncio
async def test_chunks_go_out_one_at_a_time_and_stop_at_the_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gnomad_link.api.client import CLINVAR_SUBMISSIONS_MAX_CHUNKS

    client = UnifiedGnomadClient()
    in_flight = max_in_flight = calls = 0

    async def fake_raw(
        query_string: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        nonlocal in_flight, max_in_flight, calls
        in_flight, calls = in_flight + 1, calls + 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0)
        in_flight -= 1
        return {}

    monkeypatch.setattr(client, "execute_raw_query", fake_raw)
    over = 30  # ids beyond the cap
    ids = [f"1-{i}-A-G" for i in range(24 * CLINVAR_SUBMISSIONS_MAX_CHUNKS + over)]
    result = await client.get_clinvar_submissions_batch(ids, "GRCh38")
    await client.close()

    assert max_in_flight == 1
    assert calls == CLINVAR_SUBMISSIONS_MAX_CHUNKS
    assert result.capped == over
    assert result.failed_variant_ids == ids[-over:]


@pytest.mark.asyncio
async def test_a_rate_limited_chunk_stops_the_rest(monkeypatch: pytest.MonkeyPatch) -> None:
    from gnomad_link.api import RateLimitedError

    client = UnifiedGnomadClient()
    calls = 0

    async def fake_raw(
        query_string: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RateLimitedError("budget spent")
        ids = re.findall(r'variant_id: "([^"]+)"', query_string)
        return {f"v{i}": {"variant_id": vid, "submissions": []} for i, vid in enumerate(ids)}

    monkeypatch.setattr(client, "execute_raw_query", fake_raw)
    ids = [f"1-{i}-A-G" for i in range(24 * 4)]
    result = await client.get_clinvar_submissions_batch(ids, "GRCh38")
    await client.close()

    assert calls == 2  # chunks 3 and 4 are not sent
    assert len(result) == 24
    assert result.failed_chunks == 3
    assert result.failed_variant_ids == ids[24:]
    assert result.capped == 0
