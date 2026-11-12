"""Filtering allele frequency (faf95 grpmax) + max_pop excludes 'remaining' (#125)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from gnomad_link.models import VariantDataSource, VariantFrequencyResponse
from gnomad_link.models.variant_models import PopulationFrequency
from gnomad_link.services import FrequencyService


def _pop(pid: str, ac: int, an: int) -> PopulationFrequency:
    return PopulationFrequency(id=pid, ac=ac, an=an, homozygote_count=0)


def _response(**kw: Any) -> VariantFrequencyResponse:
    exome = VariantDataSource(
        ac=12,
        an=200_000,
        populations=[
            _pop("remaining", 3, 6_000),  # 5.0e-04 -- not an ancestry group
            _pop("asj", 2, 5_000),  # 4.0e-04 -- bottlenecked, excluded from grpmax
            _pop("nfe", 7, 189_000),
        ],
    )
    return VariantFrequencyResponse(
        variant_id="12-57807649-G-T", dataset="gnomad_r4", exome=exome, genome=None, **kw
    )


def _shape(resp: VariantFrequencyResponse) -> dict[str, Any]:
    from gnomad_link.mcp.shaping import shape_variant_frequencies

    return shape_variant_frequencies(
        resp,
        populations=None,
        include_subcohorts=False,
        include_sex_split=False,
        exclude_zero_populations=True,
    )


def test_max_pop_never_reports_remaining() -> None:
    summary = _shape(_response())["summary"]
    assert summary["max_pop"] == "asj"
    assert summary["top_enriched_population"]["id"] == "asj"


def test_summary_carries_faf95_grpmax_excluding_bottlenecked_max_pop() -> None:
    faf = {
        "exome": {"grpmax": 3.4e-05, "grpmax_pop": "nfe"},
        "joint": {"grpmax": 3.2e-05, "grpmax_pop": "nfe"},
    }
    summary = _shape(_response(faf95=faf))["summary"]
    assert summary["max_pop"] == "asj"
    assert summary["faf95"] == faf


def test_summary_omits_faf95_when_upstream_has_none() -> None:
    assert "faf95" not in _shape(_response())["summary"]


@pytest.mark.asyncio
async def test_service_parses_faf95_and_skips_null_sources() -> None:
    client = MagicMock()
    client.get_variant = AsyncMock(
        return_value={
            "variant": {
                "variant_id": "12-57807649-G-T",
                "exome": {
                    "populations": [{"id": "nfe", "ac": 1, "an": 100}],
                    "faf95": {"popmax": 3.373e-05, "popmax_population": "nfe"},
                },
                "genome": {
                    "populations": [],
                    "faf95": {"popmax": None, "popmax_population": None},
                },
                "joint": {"faf95": {"popmax": 3.178e-05, "popmax_population": "nfe"}},
            }
        }
    )
    result = await FrequencyService(client=client).get_variant_frequencies(
        "12-57807649-G-T", "gnomad_r4"
    )
    assert result.faf95 == {
        "exome": {"grpmax": 3.373e-05, "grpmax_pop": "nfe"},
        "joint": {"grpmax": 3.178e-05, "grpmax_pop": "nfe"},
    }


@pytest.mark.asyncio
async def test_minimal_mode_keeps_faf95() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    faf = {"exome": {"grpmax": 3.4e-05, "grpmax_pop": "nfe"}}

    class _Stub:
        async def get_variant_frequencies(
            self, variant_id: str, dataset: str = "gnomad_r4"
        ) -> VariantFrequencyResponse:
            return _response(faf95=faf)

    mcp = create_gnomad_mcp(service_factory=lambda: _Stub())
    result = await mcp.call_tool(
        "get_variant_frequencies",
        {"variant_id": "12-57807649-G-T", "response_mode": "minimal"},
    )
    assert (result.structured_content or {})["summary"]["faf95"] == faf
