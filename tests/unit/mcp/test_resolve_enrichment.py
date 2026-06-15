"""resolve_variant_id enrichment + liftover source_genome rename tests.

Task B4 of the MCP Facade Polish plan:

1. resolve_variant_id (and the deprecated alias search_variants) now perform a
   second-pass call to FrequencyService.get_variant_frequencies for the top N
   resolved IDs to attach gene_symbol, major_consequence, and AF. Enrichment is
   capped at the first 5 results and tolerates per-variant failures via
   _meta.enrichment_partial. Pass enrich=False to opt out entirely.

2. compute_variant_liftover takes the canonical source_genome parameter. The
   legacy reference_genome alias was dropped under the Tool-Naming Standard v1
   major release (no deprecation shim).
"""

from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.models import VariantFrequencyResponse
from gnomad_link.models.variant_models import VariantDataSource


def _make_freq_response(
    variant_id: str,
    *,
    gene_symbol: str | None = "PCSK9",
    major_consequence: str | None = "frameshift_variant",
    ac: int = 1,
    an: int = 10000,
) -> VariantFrequencyResponse:
    return VariantFrequencyResponse(
        variant_id=variant_id,
        dataset="gnomad_r4",
        gene_symbol=gene_symbol,
        major_consequence=major_consequence,
        exome=VariantDataSource(ac=ac, an=an, homozygote_count=0, populations=[]),
        genome=None,
    )


class _StubService:
    """FrequencyService stub for enrichment tests."""

    def __init__(
        self,
        *,
        search_ids: list[str] | None = None,
        freq_factory: Any = None,
        freq_raises: BaseException | None = None,
        liftover_result: list[dict[str, Any]] | None = None,
    ) -> None:
        self._search_ids = search_ids if search_ids is not None else ["1-55051215-G-GA"]
        self._freq_factory = freq_factory
        self._freq_raises = freq_raises
        self._liftover_result = liftover_result if liftover_result is not None else []
        self.search_calls: list[tuple[str, str]] = []
        self.freq_calls: list[tuple[str, str]] = []
        self.liftover_calls: list[tuple[str, str]] = []

    async def search_variants(self, query: str, dataset: str) -> list[str]:
        self.search_calls.append((query, dataset))
        return list(self._search_ids)

    async def get_variant_frequencies(
        self, variant_id: str, dataset: str
    ) -> VariantFrequencyResponse:
        self.freq_calls.append((variant_id, dataset))
        if self._freq_raises is not None:
            raise self._freq_raises
        if self._freq_factory is None:
            return _make_freq_response(variant_id)
        result = self._freq_factory(variant_id, dataset)
        return result  # type: ignore[no-any-return]

    async def liftover_variant(
        self, source_variant_id: str, reference_genome: str
    ) -> list[dict[str, Any]]:
        self.liftover_calls.append((source_variant_id, reference_genome))
        return list(self._liftover_result)


def _structured(result: Any) -> dict[str, Any]:
    return result.structured_content or {}


# ---------------------------------------------------------------------------
# resolve_variant_id enrichment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_variant_id_enriches_with_gene_consequence_af() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubService(search_ids=["1-55051215-G-GA"])
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "resolve_variant_id", {"query": "rs11591147", "dataset": "gnomad_r4"}
    )
    payload = _structured(result)

    assert payload.get("success") is not False, payload
    assert payload["returned"] == 1
    first = payload["results"][0]
    assert first["variant_id"] == "1-55051215-G-GA"
    assert first["gene_symbol"] == "PCSK9"
    assert first["major_consequence"] == "frameshift_variant"
    assert first["af"] == pytest.approx(0.0001)
    assert first["af_source"] == "exome"
    assert stub.freq_calls == [("1-55051215-G-GA", "gnomad_r4")]


@pytest.mark.asyncio
async def test_resolve_variant_id_enrich_disabled_returns_ids_only() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubService(search_ids=["1-55051215-G-GA"])
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "resolve_variant_id",
        {"query": "rs11591147", "dataset": "gnomad_r4", "enrich": False},
    )
    payload = _structured(result)

    assert payload.get("success") is not False, payload
    assert stub.freq_calls == []
    first = payload["results"][0]
    assert first == {"variant_id": "1-55051215-G-GA"}


@pytest.mark.asyncio
async def test_resolve_variant_id_enrichment_failure_partial_meta() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubService(
        search_ids=["1-55051215-G-GA"],
        freq_raises=RuntimeError("upstream boom"),
    )
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "resolve_variant_id", {"query": "rs11591147", "dataset": "gnomad_r4"}
    )
    payload = _structured(result)

    assert payload.get("success") is not False, payload
    first = payload["results"][0]
    # Result still returned, with variant_id only (no enrichment fields populated).
    assert first["variant_id"] == "1-55051215-G-GA"
    assert first.get("gene_symbol") is None
    assert first.get("major_consequence") is None
    assert first.get("af") is None
    meta = payload.get("_meta") or {}
    assert meta.get("enrichment_partial") is True
    assert meta.get("enrichment_failures") == 1


@pytest.mark.asyncio
async def test_resolve_variant_id_caps_enrichment_at_5() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    ids = [f"1-{1000 + i}-A-T" for i in range(10)]
    stub = _StubService(search_ids=ids)
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "resolve_variant_id",
        {"query": "noisy", "dataset": "gnomad_r4", "limit": 10},
    )
    payload = _structured(result)

    assert payload["returned"] == 10
    # First 5 enriched.
    for item in payload["results"][:5]:
        assert item.get("gene_symbol") == "PCSK9"
        assert item.get("major_consequence") == "frameshift_variant"
        assert item.get("af") is not None
    # Remaining 5 returned with variant_id only.
    for item in payload["results"][5:]:
        assert item.get("gene_symbol") is None
        assert item.get("major_consequence") is None
        assert item.get("af") is None
    assert len(stub.freq_calls) == 5


@pytest.mark.asyncio
async def test_search_variants_alias_also_enriches() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubService(search_ids=["1-55051215-G-GA"])
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool("search_variants", {"query": "rs11591147", "dataset": "gnomad_r4"})
    payload = _structured(result)

    assert payload.get("success") is not False, payload
    first = payload["results"][0]
    assert first["variant_id"] == "1-55051215-G-GA"
    assert first["gene_symbol"] == "PCSK9"
    assert first["major_consequence"] == "frameshift_variant"
    assert first["af"] == pytest.approx(0.0001)
    assert first["af_source"] == "exome"
    # Alias must still carry its deprecation hint.
    meta = payload.get("_meta") or {}
    assert meta.get("deprecated") is True
    assert meta.get("use_instead") == "resolve_variant_id"


# ---------------------------------------------------------------------------
# compute_variant_liftover: canonical source_genome parameter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compute_variant_liftover_accepts_source_genome() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubService()
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "compute_variant_liftover",
        {"source_variant_id": "1-55051215-G-GA", "source_genome": "GRCh37"},
    )
    payload = _structured(result)

    assert payload.get("error_code") != "validation_failed", payload
    assert payload.get("success") is not False, payload
    assert payload["source_reference_genome"] == "GRCh37"
    assert stub.liftover_calls == [("1-55051215-G-GA", "GRCh37")]
    meta = payload.get("_meta") or {}
    assert "deprecated_params" not in meta


@pytest.mark.asyncio
async def test_compute_variant_liftover_rejects_legacy_reference_genome() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubService()
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    # The legacy reference_genome alias was dropped (no shim). Passing it as an
    # unknown argument must not silently behave like source_genome.
    result = await mcp.call_tool(
        "compute_variant_liftover",
        {"source_variant_id": "1-55051215-G-GA", "reference_genome": "GRCh37"},
    )
    payload = _structured(result)

    assert payload.get("success") is False, payload
    # source_genome was never supplied, so the build cannot be determined.
    assert stub.liftover_calls == []


@pytest.mark.asyncio
async def test_compute_variant_liftover_rejects_when_source_genome_missing() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubService()
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "compute_variant_liftover",
        {"source_variant_id": "1-55051215-G-GA"},
    )
    payload = _structured(result)

    # Either a validation envelope or a structured value-error envelope is OK.
    assert payload.get("success") is False, payload
    assert payload.get("error_code") in {"validation_failed", "internal_error"}, payload
    # Service must not have been called.
    assert stub.liftover_calls == []
