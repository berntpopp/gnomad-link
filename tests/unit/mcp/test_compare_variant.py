"""Tool-level tests for compare_variant_across_datasets.

Task C2.2 of the new-tools plan. The tool fans out get_variant_frequencies per
dataset (reusing shape_variant_frequencies), tolerates per-dataset 404s as
{present: false}, and for gnomad_r2_1 (GRCh37) with a GRCh38-style id and
auto_liftover=True converts the id first via liftover_variant.
"""

from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.api import DataNotFoundError, GnomadApiError
from gnomad_link.models import VariantDataSource, VariantFrequencyResponse
from gnomad_link.models.variant_models import PopulationFrequency


def _structured(result: Any) -> dict[str, Any]:
    return result.structured_content or {}


def _freq(
    variant_id: str,
    dataset: str,
    *,
    overall_an: int = 100_000,
    overall_ac: int = 200,
    afr_ac: int = 100,
    nfe_ac: int = 10,
) -> VariantFrequencyResponse:
    exome = VariantDataSource(
        ac=overall_ac,
        an=overall_an,
        homozygote_count=0,
        populations=[
            PopulationFrequency.model_validate(
                {"id": "afr", "ac": afr_ac, "an": 10_000, "homozygote_count": 0}
            ),
            PopulationFrequency.model_validate(
                {"id": "nfe", "ac": nfe_ac, "an": 50_000, "homozygote_count": 0}
            ),
        ],
    )
    return VariantFrequencyResponse(
        variant_id=variant_id,
        dataset=dataset,
        gene_symbol="PCSK9",
        major_consequence="missense_variant",
        exome=exome,
        genome=None,
    )


class _StubService:
    """FrequencyService stub. Maps (variant_id, dataset) -> response or raises."""

    def __init__(
        self,
        *,
        freq_by_dataset: dict[str, VariantFrequencyResponse | BaseException],
        liftover_result: list[dict[str, Any]] | None = None,
    ) -> None:
        self._freq_by_dataset = freq_by_dataset
        self._liftover_result = liftover_result if liftover_result is not None else []
        self.freq_calls: list[tuple[str, str]] = []
        self.liftover_calls: list[tuple[str, str]] = []

    async def get_variant_frequencies(
        self, variant_id: str, dataset: str
    ) -> VariantFrequencyResponse:
        self.freq_calls.append((variant_id, dataset))
        outcome = self._freq_by_dataset[dataset]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    async def liftover_variant(
        self, source_variant_id: str, reference_genome: str
    ) -> list[dict[str, Any]]:
        self.liftover_calls.append((source_variant_id, reference_genome))
        return list(self._liftover_result)


@pytest.mark.asyncio
async def test_compares_two_present_datasets_and_emits_deltas() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubService(
        freq_by_dataset={
            "gnomad_r4": _freq("1-55039974-G-T", "gnomad_r4", afr_ac=100),
            "gnomad_r3": _freq("1-55039974-G-T", "gnomad_r3", afr_ac=80),
        }
    )
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "compare_variant_across_datasets",
        {"variant_id": "1-55039974-G-T", "datasets": ["gnomad_r4", "gnomad_r3"]},
    )
    payload = _structured(result)

    assert payload.get("success") is not False, payload
    assert payload["variant_id"] == "1-55039974-G-T"
    assert payload["datasets"]["gnomad_r4"]["present"] is True
    assert payload["datasets"]["gnomad_r3"]["present"] is True
    overall = payload["comparison"]["overall_af_by_dataset"]
    assert set(overall) == {"gnomad_r4", "gnomad_r3"}
    by_pop = {row["population"]: row for row in payload["comparison"]["per_population_af_deltas"]}
    # afr: r4 100/10000 = 0.01 vs r3 80/10000 = 0.008 -> delta 0.002.
    assert abs(by_pop["afr"]["max_minus_min_delta"] - 0.002) < 1e-12


@pytest.mark.asyncio
async def test_compact_default_drops_per_dataset_populations_keeps_deltas() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubService(
        freq_by_dataset={
            "gnomad_r4": _freq("1-55039974-G-T", "gnomad_r4", afr_ac=100),
            "gnomad_r3": _freq("1-55039974-G-T", "gnomad_r3", afr_ac=80),
        }
    )
    mcp = create_gnomad_mcp(service_factory=lambda: stub)
    result = await mcp.call_tool(
        "compare_variant_across_datasets",
        {"variant_id": "1-55039974-G-T", "datasets": ["gnomad_r4", "gnomad_r3"]},
    )
    payload = _structured(result)

    # Per-dataset population arrays are dropped in the default compact mode...
    assert "populations" not in payload["datasets"]["gnomad_r4"]["exome"]
    assert "populations_note" in payload
    # ...but the per-population deltas (the actual signal) survive.
    by_pop = {row["population"]: row for row in payload["comparison"]["per_population_af_deltas"]}
    assert abs(by_pop["afr"]["max_minus_min_delta"] - 0.002) < 1e-12


@pytest.mark.asyncio
async def test_full_mode_keeps_per_dataset_populations() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubService(freq_by_dataset={"gnomad_r4": _freq("1-55039974-G-T", "gnomad_r4")})
    mcp = create_gnomad_mcp(service_factory=lambda: stub)
    result = await mcp.call_tool(
        "compare_variant_across_datasets",
        {
            "variant_id": "1-55039974-G-T",
            "datasets": ["gnomad_r4"],
            "response_mode": "full",
        },
    )
    payload = _structured(result)

    assert payload["datasets"]["gnomad_r4"]["exome"]["populations"]
    assert "populations_note" not in payload


@pytest.mark.asyncio
async def test_missing_dataset_marked_present_false_partial_success() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubService(
        freq_by_dataset={
            "gnomad_r4": _freq("1-55039974-G-T", "gnomad_r4"),
            "gnomad_r3": DataNotFoundError("not in r3"),
        }
    )
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "compare_variant_across_datasets",
        {"variant_id": "1-55039974-G-T", "datasets": ["gnomad_r4", "gnomad_r3"]},
    )
    payload = _structured(result)

    assert payload.get("success") is not False, payload
    assert payload["datasets"]["gnomad_r4"]["present"] is True
    assert payload["datasets"]["gnomad_r3"] == {"present": False}
    # Only the present dataset contributes to overall comparison.
    assert set(payload["comparison"]["overall_af_by_dataset"]) == {"gnomad_r4"}


@pytest.mark.asyncio
async def test_all_datasets_missing_returns_upstream_unavailable() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    # A real upstream error (GnomadApiError), NOT DataNotFoundError: the latter is
    # classified as "dataset absent" (partial success), whereas an upstream failure
    # for EVERY dataset is what collapses the whole call to upstream_unavailable.
    stub = _StubService(
        freq_by_dataset={
            "gnomad_r4": GnomadApiError("upstream 503"),
            "gnomad_r3": GnomadApiError("upstream 503"),
        }
    )
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "compare_variant_across_datasets",
        {"variant_id": "1-55039974-G-T", "datasets": ["gnomad_r4", "gnomad_r3"]},
    )
    payload = _structured(result)

    assert payload["success"] is False
    assert payload["error_code"] == "upstream_unavailable"


@pytest.mark.asyncio
async def test_auto_liftover_converts_grch38_id_for_r2_1() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubService(
        freq_by_dataset={
            "gnomad_r4": _freq("17-7673803-G-A", "gnomad_r4"),
            "gnomad_r2_1": _freq("17-7577121-G-A", "gnomad_r2_1"),
        },
        liftover_result=[
            {
                "source": {"variant_id": "17-7577121-G-A", "reference_genome": "GRCh37"},
                "liftover": {"variant_id": "17-7673803-G-A", "reference_genome": "GRCh38"},
                "datasets": ["gnomad_r2_1", "gnomad_r4"],
            }
        ],
    )
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "compare_variant_across_datasets",
        {
            "variant_id": "17-7673803-G-A",
            "datasets": ["gnomad_r4", "gnomad_r2_1"],
            "auto_liftover": True,
        },
    )
    payload = _structured(result)

    assert payload.get("success") is not False, payload
    # Liftover was invoked GRCh38 -> GRCh37 for the r2_1 leg.
    assert stub.liftover_calls == [("17-7673803-G-A", "GRCh38")]
    # The r2_1 frequency lookup used the lifted GRCh37 id.
    assert ("17-7577121-G-A", "gnomad_r2_1") in stub.freq_calls
    r2 = payload["datasets"]["gnomad_r2_1"]
    assert r2["present"] is True
    assert r2["lifted_variant_id"] == "17-7577121-G-A"
    assert any("GRCh37" in note for note in payload["build_notes"])


@pytest.mark.asyncio
async def test_auto_liftover_no_mapping_marks_r2_1_present_false() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubService(
        freq_by_dataset={
            "gnomad_r4": _freq("17-7673803-G-A", "gnomad_r4"),
            # r2_1 should never be queried because liftover yields no mapping.
            "gnomad_r2_1": _freq("unused", "gnomad_r2_1"),
        },
        liftover_result=[],
    )
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "compare_variant_across_datasets",
        {
            "variant_id": "17-7673803-G-A",
            "datasets": ["gnomad_r4", "gnomad_r2_1"],
            "auto_liftover": True,
        },
    )
    payload = _structured(result)

    assert payload.get("success") is not False, payload
    assert payload["datasets"]["gnomad_r2_1"] == {"present": False}
    assert stub.liftover_calls == [("17-7673803-G-A", "GRCh38")]
    # r2_1 frequencies never fetched (no lifted id).
    assert all(d != "gnomad_r2_1" for _, d in stub.freq_calls)


@pytest.mark.asyncio
async def test_next_commands_point_to_clinvar_and_carrier() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubService(freq_by_dataset={"gnomad_r4": _freq("1-55039974-G-T", "gnomad_r4")})
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "compare_variant_across_datasets",
        {"variant_id": "1-55039974-G-T", "datasets": ["gnomad_r4"]},
    )
    payload = _structured(result)

    next_tools = [cmd["tool"] for cmd in payload["_meta"]["next_commands"]]
    assert "get_clinvar_variant_details" in next_tools
    assert "compute_carrier_frequency" in next_tools
    assert "compare_variant_across_datasets" not in next_tools  # no self-reference
    assert len(next_tools) <= 3
    # Research-use meta is preserved by run_mcp_tool.
    assert payload["_meta"]["unsafe_for_clinical_use"] is True


@pytest.mark.asyncio
async def test_tool_has_read_only_open_world_annotations_and_tag() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubService(freq_by_dataset={})
    mcp = create_gnomad_mcp(service_factory=lambda: stub)
    tools_by_name = {tool.name: tool for tool in await mcp.list_tools()}
    tool = tools_by_name["compare_variant_across_datasets"]

    assert tool.tags == {"variant"}
    assert tool.annotations is not None
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.openWorldHint is True
    # Tool-Surface-Budget v1: outputSchema is suppressed (no model reads it).
    assert tool.output_schema is None


@pytest.mark.asyncio
async def test_compare_r2_1_uses_grch37_source_not_input_coordinate() -> None:
    """Regression: the r2_1 leg must use the GRCh37 `source` id, not the GRCh38 input."""
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubService(
        freq_by_dataset={
            "gnomad_r4": _freq("6-26092913-G-A", "gnomad_r4"),
            "gnomad_r2_1": _freq("6-26093141-G-A", "gnomad_r2_1"),
        },
        liftover_result=[
            {
                "source": {"variant_id": "6-26093141-G-A", "reference_genome": "GRCh37"},
                "liftover": {"variant_id": "6-26092913-G-A", "reference_genome": "GRCh38"},
                "datasets": ["gnomad_r2_1", "gnomad_r4"],
            }
        ],
    )
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "compare_variant_across_datasets",
        {
            "variant_id": "6-26092913-G-A",
            "datasets": ["gnomad_r4", "gnomad_r2_1"],
            "auto_liftover": True,
        },
    )
    payload = _structured(result)

    assert payload["datasets"]["gnomad_r2_1"]["present"] is True
    assert ("6-26093141-G-A", "gnomad_r2_1") in stub.freq_calls
    assert ("6-26092913-G-A", "gnomad_r2_1") not in stub.freq_calls
    assert any("6-26093141-G-A" in note for note in payload["build_notes"])
