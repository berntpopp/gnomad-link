"""Mitochondrial heteroplasmy zero-bin trimming tests.

Hot-Fix H3: the gnomAD GraphQL ``heteroplasmy_distribution`` histogram ships
many empty bins by default, ballooning the mitochondrial variant payload past
the advertised ~2-4 kB target. The MCP tool must trim zero-count bins at both
the variant-level and per-population scope by default, and expose
``include_heteroplasmy_zeros=True`` as an opt-out. When trimming fires, a
self-describing ``truncated.kind="heteroplasmy_zeros"`` block reports the
total count and the restoration knob.
"""

from __future__ import annotations

from typing import Any

import pytest


class _SpyMitoService:
    """Stub FrequencyService that returns a canned mitochondrial payload."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.last_variant_id: str | None = None
        self.last_dataset: str | None = None

    async def get_mitochondrial_variant(self, variant_id: str, dataset: str) -> dict[str, Any]:
        self.last_variant_id = variant_id
        self.last_dataset = dataset
        return {"mitochondrial_variant": self.payload}


def _variant_payload(
    *,
    variant_dist: dict[str, Any] | None,
    pop_dists: list[dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    """Build a minimal mitochondrial_variant payload for stubbing."""

    populations: list[dict[str, Any]] = []
    if pop_dists is not None:
        for idx, dist in enumerate(pop_dists):
            pop: dict[str, Any] = {
                "id": f"pop{idx}",
                "an": 100,
                "ac_het": 5,
                "ac_hom": 0,
            }
            if dist is not None:
                pop["heteroplasmy_distribution"] = dist
            populations.append(pop)
    payload: dict[str, Any] = {
        "variant_id": "M-3243-A-G",
        "pos": 3243,
        "ref": "A",
        "alt": "G",
        "ac_het": 5,
        "ac_hom": 0,
        "an": 100,
        "populations": populations,
    }
    if variant_dist is not None:
        payload["heteroplasmy_distribution"] = variant_dist
    return payload


def test_trim_heteroplasmy_distribution_drops_zero_bins() -> None:
    from gnomad_link.mcp.shaping import trim_heteroplasmy_distribution

    dist = {"bin_edges": [0.0, 0.1, 0.2, 0.3, 0.4], "bin_freq": [0, 5, 0, 3, 0]}

    trimmed, dropped = trim_heteroplasmy_distribution(dist)

    assert trimmed == {"bin_edges": [0.1, 0.3], "bin_freq": [5, 3]}
    assert dropped == 3


def test_trim_handles_real_gnomad_n_plus_one_edges() -> None:
    """Real gnomAD histograms ship N+1 bin_edges for N bin_freq; trimming must fire.

    Regression: the length guard required len(edges) == len(freqs), which is never
    true for live data (11 edges, 10 freqs), so zero-bin trimming silently never
    fired in production.
    """
    from gnomad_link.mcp.shaping import trim_heteroplasmy_distribution

    dist = {
        "bin_edges": [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],  # 11
        "bin_freq": [0, 1, 1, 0, 0, 0, 0, 0, 0, 0],  # 10
    }

    trimmed, dropped = trim_heteroplasmy_distribution(dist)

    assert trimmed == {"bin_edges": [0.1, 0.2], "bin_freq": [1, 1]}
    assert dropped == 8


def test_trim_drops_all_zero_real_gnomad_histogram() -> None:
    from gnomad_link.mcp.shaping import trim_heteroplasmy_distribution

    dist = {
        "bin_edges": [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        "bin_freq": [0] * 10,
    }

    trimmed, dropped = trim_heteroplasmy_distribution(dist)

    assert trimmed is None
    assert dropped == 10


def test_trim_returns_none_when_all_zero() -> None:
    from gnomad_link.mcp.shaping import trim_heteroplasmy_distribution

    trimmed, dropped = trim_heteroplasmy_distribution({"bin_edges": [0.0, 0.1], "bin_freq": [0, 0]})

    assert trimmed is None
    assert dropped == 2


def test_trim_preserves_non_bin_fields() -> None:
    from gnomad_link.mcp.shaping import trim_heteroplasmy_distribution

    dist = {
        "bin_edges": [0.0, 0.1],
        "bin_freq": [0, 5],
        "n_smaller": 0,
        "n_larger": 0,
    }

    trimmed, dropped = trim_heteroplasmy_distribution(dist)

    assert trimmed is not None
    assert trimmed["bin_edges"] == [0.1]
    assert trimmed["bin_freq"] == [5]
    assert trimmed["n_smaller"] == 0
    assert trimmed["n_larger"] == 0
    assert dropped == 1


def test_trim_handles_missing_keys() -> None:
    from gnomad_link.mcp.shaping import trim_heteroplasmy_distribution

    # None passes through unchanged.
    assert trim_heteroplasmy_distribution(None) == (None, 0)

    # Empty dict passes through (no bin_edges / bin_freq).
    assert trim_heteroplasmy_distribution({}) == ({}, 0)

    # Missing bin_edges: return input unchanged.
    only_freq = {"bin_freq": [0]}
    assert trim_heteroplasmy_distribution(only_freq) == (only_freq, 0)


@pytest.mark.asyncio
async def test_get_mitochondrial_variant_trims_zeros_by_default() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    edges = [round(i * 0.1, 1) for i in range(10)]
    freqs = [0, 5, 0, 0, 3, 0, 0, 2, 0, 0]  # 7 zero bins, 3 non-zero
    spy = _SpyMitoService(_variant_payload(variant_dist={"bin_edges": edges, "bin_freq": freqs}))
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "get_mitochondrial_variant",
        {"variant_id": "M-3243-A-G", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    assert payload.get("error_code") != "validation_failed", payload
    dist = payload.get("heteroplasmy_distribution")
    assert dist is not None
    assert dist["bin_freq"] == [5, 3, 2]
    assert dist["bin_edges"] == [0.1, 0.4, 0.7]
    truncated = payload.get("truncated")
    assert isinstance(truncated, dict)
    assert truncated["kind"] == "heteroplasmy_zeros"
    assert truncated["dropped"] == 7
    assert truncated["to_restore"] == "include_heteroplasmy_zeros=True"


@pytest.mark.asyncio
async def test_get_mitochondrial_variant_include_heteroplasmy_zeros_passes_through() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    edges = [round(i * 0.1, 1) for i in range(10)]
    freqs = [0, 5, 0, 0, 3, 0, 0, 2, 0, 0]
    spy = _SpyMitoService(_variant_payload(variant_dist={"bin_edges": edges, "bin_freq": freqs}))
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "get_mitochondrial_variant",
        {
            "variant_id": "M-3243-A-G",
            "dataset": "gnomad_r4",
            "include_heteroplasmy_zeros": True,
        },
    )
    payload = result.structured_content or {}

    assert payload.get("error_code") != "validation_failed", payload
    dist = payload.get("heteroplasmy_distribution")
    assert dist is not None
    assert dist["bin_edges"] == edges
    assert dist["bin_freq"] == freqs
    truncated = payload.get("truncated")
    if isinstance(truncated, dict):
        assert truncated.get("kind") != "heteroplasmy_zeros"


@pytest.mark.asyncio
async def test_per_population_heteroplasmy_also_trimmed() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    pop_dist_a = {
        "bin_edges": [0.0, 0.1, 0.2, 0.3],
        "bin_freq": [0, 4, 0, 0],
    }
    pop_dist_b = {
        "bin_edges": [0.0, 0.1, 0.2],
        "bin_freq": [0, 0, 2],
    }
    spy = _SpyMitoService(
        _variant_payload(
            variant_dist={"bin_edges": [0.0, 0.1], "bin_freq": [0, 1]},
            pop_dists=[pop_dist_a, pop_dist_b],
        )
    )
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "get_mitochondrial_variant",
        {"variant_id": "M-3243-A-G", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    populations = payload.get("populations") or []
    assert len(populations) == 2
    assert populations[0]["heteroplasmy_distribution"] == {
        "bin_edges": [0.1],
        "bin_freq": [4],
    }
    assert populations[1]["heteroplasmy_distribution"] == {
        "bin_edges": [0.2],
        "bin_freq": [2],
    }
    truncated = payload.get("truncated")
    assert isinstance(truncated, dict)
    assert truncated["kind"] == "heteroplasmy_zeros"
    # 1 (variant) + 3 (pop a) + 2 (pop b) = 6 dropped bins total.
    assert truncated["dropped"] == 6


@pytest.mark.asyncio
async def test_drops_heteroplasmy_when_all_bins_zero() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    all_zero = {"bin_edges": [0.0, 0.1, 0.2], "bin_freq": [0, 0, 0]}
    spy = _SpyMitoService(_variant_payload(variant_dist=all_zero))
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "get_mitochondrial_variant",
        {"variant_id": "M-3243-A-G", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    assert "heteroplasmy_distribution" not in payload
    truncated = payload.get("truncated")
    assert isinstance(truncated, dict)
    assert truncated["kind"] == "heteroplasmy_zeros"
    assert truncated["dropped"] == 3
