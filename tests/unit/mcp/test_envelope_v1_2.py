"""Response-Envelope Standard v1.2: provenance on every success, checked against the schema.

The schema is vendored from berntpopp/genefoundry-envelope, tag v1.2.0. ``tests/conftest.py``
validates every tool result the suite produces against it; this file pins the schema file,
the three provenance fields and the cache rule for ``retrieved_at``.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from gnomad_link.api import note_fetch
from gnomad_link.mcp.errors import run_mcp_tool
from gnomad_link.mcp.facade import create_gnomad_mcp
from gnomad_link.mcp.resources import GNOMAD_DATA_RELEASE
from gnomad_link.models import (
    ClinVarCondition,
    ClinVarSubmission,
    ClinVarVariant,
    VariantFrequencyResponse,
)
from gnomad_link.services.absent_cache import AbsentCache, FetchTimeCache

CONFORMANCE = Path(__file__).parents[2] / "conformance"
VARIANT_ID = "1-55051215-G-GA"


class _StubService:
    async def get_variant_frequencies(
        self, variant_id: str, dataset: str
    ) -> VariantFrequencyResponse:
        return VariantFrequencyResponse(
            variant_id=variant_id, dataset=dataset, exome=None, genome=None
        )

    async def get_clinvar_variant(self, variant_id: str, reference_genome: str) -> ClinVarVariant:
        submission = ClinVarSubmission(
            clinical_significance="Pathogenic",
            submitter_name="A laboratory",
            conditions=[ClinVarCondition(name="A condition", medgen_id="C0027672")],
        )
        return ClinVarVariant(
            variant_id=variant_id,
            reference_genome=reference_genome,
            chrom="1",
            pos=55051215,
            ref="G",
            alt="GA",
            clinical_significance="Pathogenic",
            clinvar_variation_id="12345",
            submissions=[submission],
        )


async def _call(tool: str, **arguments: Any) -> dict[str, Any]:
    mcp = create_gnomad_mcp(service_factory=lambda: _StubService())  # type: ignore[arg-type,return-value]
    result = await mcp.call_tool(tool, {"variant_id": VARIANT_ID, **arguments})
    return result.structured_content or {}


def test_vendored_schema_is_the_v1_2_0_release() -> None:
    digest = hashlib.sha256((CONFORMANCE / "envelope-v1.2.schema.json").read_bytes()).hexdigest()
    assert digest == (CONFORMANCE / "envelope-v1.2.schema.sha256").read_text().strip()
    assert digest == "c3c47e20d7dd189aac2568fc963b5514d7a5ac2c3e5f21d126f42c96d1ad1ae3"


async def test_success_carries_the_three_provenance_fields(schema_errors: Any) -> None:
    envelope = await _call("get_variant_frequencies", dataset="gnomad_r4")

    assert envelope["success"] is True
    assert schema_errors(envelope) == []
    meta = envelope["_meta"]
    assert meta["source"] == "gnomad"
    assert meta["data_version"] == GNOMAD_DATA_RELEASE
    assert meta["retrieved_at"].endswith("Z")
    assert all(meta[key] for key in ("source", "data_version", "retrieved_at", "request_id"))
    assert meta["gnomad_release"] == GNOMAD_DATA_RELEASE  # the older name stays next to it


async def test_error_validates_without_provenance(schema_errors: Any) -> None:
    envelope = await _call("get_variant_frequencies", dataset="not-a-dataset")

    assert envelope["success"] is False
    assert schema_errors(envelope) == []
    assert "retrieved_at" not in envelope["_meta"]


def test_the_schema_rejects_a_success_without_provenance(schema_errors: Any) -> None:
    envelope = {"success": True, "result": {}, "_meta": {"request_id": "r", "elapsed_ms": 1}}
    assert len(schema_errors(envelope)) == 3


async def test_retrieved_at_is_the_oldest_upstream_fetch() -> None:
    async def call() -> dict[str, Any]:
        note_fetch(1_700_000_100.0)
        note_fetch(1_700_000_000.0)
        return {"result": {}}

    assert (await run_mcp_tool("t", call))["_meta"]["retrieved_at"] == "2023-11-14T22:13:20Z"


async def test_a_cache_hit_keeps_the_time_of_the_fetch_that_filled_it() -> None:
    fetches = [1_700_000_000.0, 1_600_000_000.0]

    async def impl(key: str) -> list[str]:
        note_fetch(fetches.pop(0))
        return [key] if key == "hit" else []

    cached = FetchTimeCache(impl, 8, 60)
    absent = AbsentCache(8)

    async def stamp(key: str) -> str:
        async def call() -> dict[str, Any]:
            return {"results": await absent.call(cached, key)}

        return str((await run_mcp_tool("t", call))["_meta"]["retrieved_at"])

    assert await stamp("hit") == await stamp("hit") == "2023-11-14T22:13:20Z"
    assert len(fetches) == 1  # the second call was served from the cache
    # An empty answer replayed from the negative cache is dated to when it was stored.
    await stamp("miss")
    stored_at = absent._entries[(cached, "miss")][2]
    replayed = datetime.fromisoformat(await stamp("miss")).timestamp()
    assert fetches == [] and int(stored_at) == replayed


@pytest.mark.parametrize("mode", ["compact", "full"])
async def test_clinvar_validates_in_both_modes(schema_errors: Any, mode: str) -> None:
    envelope = await _call("get_clinvar_variant_details", response_mode=mode)
    assert schema_errors(envelope) == []
