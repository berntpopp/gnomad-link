"""Build-mismatch detection tests (Task B1).

When a caller passes a CHROM-POS-REF-ALT id whose position is unambiguously
beyond one build's chromosome length but within the other's, the MCP facade
short-circuits the upstream call with a structured `build_mismatch` envelope
that points to `liftover_variant`. Ambiguous positions (within both builds)
fall through to the upstream service unchanged.
"""

from __future__ import annotations

import pytest


class _Spy:
    """Stub FrequencyService that records whether it was called."""

    def __init__(self) -> None:
        self.last_variant_id: str | None = None
        self.last_dataset: str | None = None
        self.last_region: tuple[str, int, int, str] | None = None

    async def get_variant_frequencies(self, variant_id: str, dataset: str) -> object:
        from gnomad_link.models import VariantFrequencyResponse

        self.last_variant_id = variant_id
        self.last_dataset = dataset
        return VariantFrequencyResponse(
            variant_id=variant_id, dataset=dataset, exome=None, genome=None
        )

    async def get_variant(self, variant_id: str, dataset: str) -> dict[str, object]:
        self.last_variant_id = variant_id
        self.last_dataset = dataset
        return {"variant_id": variant_id, "dataset": dataset}

    async def liftover_variant(
        self, source_variant_id: str, reference_genome: str
    ) -> list[dict[str, object]]:
        self.last_variant_id = source_variant_id
        return []

    async def get_region(
        self, chrom: str, start: int, stop: int, dataset: str
    ) -> dict[str, object]:
        self.last_region = (chrom, start, stop, dataset)
        return {"region": {"chrom": chrom, "start": start, "stop": stop}}


def _is_build_mismatch(payload: dict[str, object]) -> bool:
    return (
        isinstance(payload, dict)
        and payload.get("success") is False
        and payload.get("error_code") == "build_mismatch"
    )


@pytest.mark.asyncio
async def test_get_variant_frequencies_detects_grch37_only_position_against_r4() -> None:
    """chr1:249_100_000 is beyond GRCh38 chr1 (248_956_422) but within GRCh37's 249_250_621."""

    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _Spy()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "get_variant_frequencies",
        {"variant_id": "1-249100000-A-T", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    assert _is_build_mismatch(payload), payload
    assert payload.get("retryable") is False
    assert payload.get("fallback_tool") == "liftover_variant"
    assert payload.get("fallback_args") == {
        "source_variant_id": "1-249100000-A-T",
        "reference_genome": "GRCh37",
    }
    recovery = str(payload.get("recovery", ""))
    assert "liftover" in recovery.lower() or "GRCh37" in recovery
    # Service must NOT have been called.
    assert spy.last_variant_id is None


@pytest.mark.asyncio
async def test_get_variant_frequencies_passes_through_grch38_only_position_against_r4() -> None:
    """chr5:181_000_000 is GRCh38-only (within 181_538_259, beyond GRCh37's 180_915_260).

    Against gnomad_r4 (GRCh38) this should pass through unchanged.
    """

    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _Spy()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "get_variant_frequencies",
        {"variant_id": "5-181000000-A-T", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    assert payload.get("error_code") != "build_mismatch", payload
    assert spy.last_variant_id == "5-181000000-A-T"


@pytest.mark.asyncio
async def test_get_variant_frequencies_passes_through_ambiguous_position() -> None:
    """1-55051215 is well within both builds; check must return None and call upstream."""

    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _Spy()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "get_variant_frequencies",
        {"variant_id": "1-55051215-G-GA", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    assert payload.get("error_code") != "build_mismatch", payload
    assert spy.last_variant_id == "1-55051215-G-GA"


@pytest.mark.asyncio
async def test_get_variant_frequencies_detects_grch38_only_position_against_r2_1() -> None:
    """chr5:181_000_000 against gnomad_r2_1 (GRCh37) is a mismatch toward GRCh38."""

    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _Spy()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "get_variant_frequencies",
        {"variant_id": "5-181000000-A-T", "dataset": "gnomad_r2_1"},
    )
    payload = result.structured_content or {}

    assert _is_build_mismatch(payload), payload
    assert payload.get("fallback_args") == {
        "source_variant_id": "5-181000000-A-T",
        "reference_genome": "GRCh38",
    }
    assert spy.last_variant_id is None


@pytest.mark.asyncio
async def test_no_build_check_on_mitochondrial() -> None:
    """liftover_variant on mito coords must not produce a build_mismatch."""

    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _Spy()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "liftover_variant",
        {"source_variant_id": "MT-7497-G-A", "reference_genome": "GRCh37"},
    )
    payload = result.structured_content or {}

    assert payload.get("error_code") != "build_mismatch", payload


@pytest.mark.asyncio
async def test_build_check_on_get_region() -> None:
    """get_region with a GRCh37-only start against gnomad_r4 must short-circuit."""

    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _Spy()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "get_region",
        {
            "region": "1-249100000-249100100",
            "dataset": "gnomad_r4",
            "include_clinvar": False,
            "include_genes": False,
        },
    )
    payload = result.structured_content or {}

    assert _is_build_mismatch(payload), payload
    assert payload.get("fallback_tool") == "liftover_variant"
    assert spy.last_region is None
