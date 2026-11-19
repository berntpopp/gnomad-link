"""Issue #145: a variant not_found checks the other genome build once and says so."""

from __future__ import annotations

import pytest

from gnomad_link.api import RateLimitedError, VariantNotFoundError
from gnomad_link.mcp.facade import create_gnomad_mcp
from gnomad_link.models import VariantFrequencyResponse


class _BuildAwareService:
    """Stub FrequencyService that only knows a variant in the given datasets."""

    def __init__(self, present_in: set[str], probe_error: Exception | None = None) -> None:
        self.present_in = present_in
        self.probe_error = probe_error
        self.calls: list[str] = []

    async def get_variant_frequencies(
        self, variant_id: str, dataset: str
    ) -> VariantFrequencyResponse:
        self.calls.append(dataset)
        if len(self.calls) > 1 and self.probe_error is not None:
            raise self.probe_error
        if dataset not in self.present_in:
            raise VariantNotFoundError(f"Variant {variant_id} not found in {dataset}")
        return VariantFrequencyResponse(
            variant_id=variant_id, dataset=dataset, exome=None, genome=None
        )


async def _call(service: _BuildAwareService, dataset: str) -> dict:
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool(
        "get_variant_frequencies", {"variant_id": "9-99694174-C-T", "dataset": dataset}
    )
    return result.structured_content or {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("asked", "found", "found_build"),
    [("gnomad_r4", "gnomad_r2_1", "GRCh37"), ("gnomad_r2_1", "gnomad_r4", "GRCh38")],
)
async def test_not_found_names_the_other_build(asked: str, found: str, found_build: str) -> None:
    service = _BuildAwareService({found})
    payload = await _call(service, asked)

    assert payload["error_code"] == "not_found"
    assert payload["found_in"] == {"dataset": found, "reference_genome": found_build}
    assert f"exists in {found} ({found_build})" in payload["message"]
    recall = {"variant_id": "9-99694174-C-T", "dataset": found}
    assert payload["fallback_tool"] == "get_variant_frequencies"
    assert payload["fallback_args"] == recall
    assert payload["_meta"]["next_commands"][0] == {
        "tool": "get_variant_frequencies",
        "arguments": recall,
    }
    assert service.calls == [asked, found]  # exactly one extra lookup


@pytest.mark.asyncio
async def test_not_found_in_both_builds_says_so() -> None:
    service = _BuildAwareService(set())
    payload = await _call(service, "gnomad_r4")

    assert payload["error_code"] == "not_found"
    assert "found_in" not in payload
    assert "in both builds" in payload["message"]
    assert service.calls == ["gnomad_r4", "gnomad_r2_1"]


@pytest.mark.asyncio
async def test_failed_probe_keeps_the_plain_not_found() -> None:
    service = _BuildAwareService(set(), probe_error=RateLimitedError("429"))
    payload = await _call(service, "gnomad_r4")

    assert payload["error_code"] == "not_found"
    assert "found_in" not in payload
    assert "in both builds" not in payload["message"]
    assert payload["fallback_tool"] == "resolve_variant_id"
