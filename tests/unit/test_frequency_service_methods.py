"""Tests for the thin service-layer wrappers added in Task 4.

These tests cover only the 8 NEW methods appended to FrequencyService.
Three methods from the original plan (get_gene, search_variants,
get_clinvar_variant) already existed in FrequencyService with richer
semantics (domain-model returns and caching); they are NOT duplicated.

Signature alignments vs plan:
- get_clinvar_variant: client takes (variant_id, reference_genome=None,
  dataset=None) — the existing service method already covers this; the new
  wrapper is NOT added to avoid a name collision.
- get_transcript: client takes (transcript_id, reference_genome=None,
  dataset=None) — wrapper uses the same 2-arg positional call style but
  only exposes transcript_id + optional reference_genome (no dataset kwarg
  forwarded, matching the plan's intended surface).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from gnomad_link.services.frequency_service import FrequencyService


@pytest.fixture
def service_with_stub_client():
    client = AsyncMock()
    return FrequencyService(client=client), client


@pytest.mark.asyncio
async def test_get_variant_delegates_to_client(service_with_stub_client) -> None:
    service, client = service_with_stub_client
    client.get_variant.return_value = {"variant_id": "1-1-A-T"}

    result = await service.get_variant("1-1-A-T", "gnomad_r4")

    client.get_variant.assert_awaited_once_with("1-1-A-T", "gnomad_r4")
    assert result["variant_id"] == "1-1-A-T"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "service_method,client_method,args",
    [
        ("get_gene_variants", "get_gene_variants", ("ENSG1", "gnomad_r4")),
        ("get_clinvar_meta", "get_meta", ()),
        ("get_structural_variant", "get_structural_variant", ("SV_1", "gnomad_sv_r4")),
        ("get_mitochondrial_variant", "get_mitochondrial_variant", ("M-1-A-T", "gnomad_r4")),
        ("get_region", "get_region", ("1", 1, 100, "gnomad_r4")),
        ("get_transcript", "get_transcript", ("ENST1", "GRCh38")),
        ("liftover_variant", "get_liftover", ("1-1-A-T", "GRCh38")),
    ],
)
async def test_service_methods_delegate(
    service_with_stub_client, service_method, client_method, args
) -> None:
    service, client = service_with_stub_client
    getattr(client, client_method).return_value = {"ok": True}

    result = await getattr(service, service_method)(*args)

    getattr(client, client_method).assert_awaited_once_with(*args)
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_search_genes_is_cached_but_errors_are_not(service_with_stub_client) -> None:
    """Issue #140: repeated gene searches hit upstream once; a failure is not cached."""
    service, client = service_with_stub_client
    hit = {"ensembl_id": "ENSG00000169174", "symbol": "PCSK9"}
    client.search_genes.side_effect = [RuntimeError("429"), [hit]]

    with pytest.raises(RuntimeError):
        await service.search_genes("PCSK9", "GRCh38")
    first = await service.search_genes("PCSK9", "GRCh38")
    second = await service.search_genes("PCSK9", "GRCh38")

    assert first == second and first[0].symbol == "PCSK9"
    assert client.search_genes.await_count == 2  # the error, then ONE cached fetch


@pytest.mark.asyncio
async def test_cache_ttl_minutes_is_applied() -> None:
    """Issue #140: CACHE_TTL_MINUTES was dead config; cached entries now expire."""
    import asyncio

    client = AsyncMock()
    client.search_genes.return_value = [{"ensembl_id": "ENSG1", "symbol": "X"}]
    service = FrequencyService(client=client, gene_search_cache_ttl_minutes=0.0005)  # type: ignore[arg-type]

    await service.search_genes("X")
    await service.search_genes("X")
    assert client.search_genes.await_count == 1  # hit within the TTL
    await asyncio.sleep(0.1)  # TTL is 30 ms
    await service.search_genes("X")
    assert client.search_genes.await_count == 2  # expired -> refetched


@pytest.mark.asyncio
async def test_search_genes_key_ignores_case_and_whitespace(service_with_stub_client) -> None:
    """#155: search_genes("pcsk9") after search_genes("PCSK9") makes 0 upstream requests."""
    service, client = service_with_stub_client
    client.search_genes.return_value = [{"ensembl_id": "ENSG00000169174", "symbol": "PCSK9"}]

    await service.search_genes("PCSK9", "GRCh38")
    await service.search_genes("pcsk9", "GRCh38")
    await service.search_genes(" Pcsk9 ", "GRCh38")

    client.search_genes.assert_awaited_once_with("PCSK9", "GRCh38")


@pytest.mark.asyncio
async def test_search_variants_is_cached(service_with_stub_client) -> None:
    service, client = service_with_stub_client
    client.search_variants.return_value = [{"variant_id": "1-55051215-G-GA"}]

    first = await service.search_variants("rs11591147", "gnomad_r4")
    first.append("mutated by a caller")
    second = await service.search_variants("rs11591147", "gnomad_r4")

    assert second == ["1-55051215-G-GA"]
    assert client.search_variants.await_count == 1


@pytest.mark.asyncio
async def test_empty_and_not_found_answers_are_kept_only_briefly(monkeypatch) -> None:
    """#155: a short-TTL negative cache; the long positive TTL never holds an empty answer."""
    import gnomad_link.services.absent_cache as ac
    from gnomad_link.api.base_client import VariantNotFoundError

    clock = [1000.0]
    monkeypatch.setattr(ac.time, "monotonic", lambda: clock[0])
    client = AsyncMock()
    client.search_genes.return_value = []
    client.search_variants.return_value = []
    client.get_variant.side_effect = VariantNotFoundError("absent")
    service = FrequencyService(client=client)

    for _ in range(2):
        assert await service.search_genes("NOPE1") == []
        assert await service.search_variants("rs1", "gnomad_r4") == []
        with pytest.raises(VariantNotFoundError):
            await service.get_variant_frequencies("1-1-A-T")
    assert (client.search_genes.await_count, client.search_variants.await_count) == (1, 1)
    assert client.get_variant.await_count == 1

    clock[0] += ac.NEGATIVE_TTL_SECONDS + 1
    await service.search_genes("NOPE1")
    with pytest.raises(VariantNotFoundError):
        await service.get_variant_frequencies("1-1-A-T")
    assert (client.search_genes.await_count, client.get_variant.await_count) == (2, 2)
