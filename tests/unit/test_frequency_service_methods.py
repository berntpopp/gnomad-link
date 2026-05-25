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
