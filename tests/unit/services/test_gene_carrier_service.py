from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.services.gene_carrier_filters import FilterConfig
from gnomad_link.services.gene_carrier_service import GeneCarrierService


def _joint(ac: int, an: int, hom: int, pops: dict[str, tuple[int, int, int]]) -> dict[str, Any]:
    return {
        "ac": ac,
        "an": an,
        "homozygote_count": hom,
        "filters": [],
        "populations": [
            {"id": pid, "ac": p[0], "an": p[1], "homozygote_count": p[2]} for pid, p in pops.items()
        ],
    }


def _gene_payload() -> dict[str, Any]:
    return {
        "gene": {
            "gene_id": "ENSG00000001626",
            "symbol": "CFTR",
            "variants": [
                {
                    "variant_id": "7-1-A-T",
                    "transcript_consequence": {
                        "is_canonical": True,
                        "lof": "HC",
                        "consequence_terms": ["stop_gained"],
                    },
                    "joint": _joint(100, 10000, 0, {"nfe": (80, 8000, 0), "afr": (20, 2000, 0)}),
                },
                {
                    "variant_id": "7-2-C-G",
                    "transcript_consequence": {
                        "is_canonical": True,
                        "lof": None,
                        "consequence_terms": ["missense_variant"],
                    },
                    "joint": _joint(50, 10000, 5, {"nfe": (50, 8000, 5)}),
                },
                {
                    # synonymous, no clinvar -> must NOT qualify
                    "variant_id": "7-3-G-A",
                    "transcript_consequence": {
                        "is_canonical": True,
                        "lof": None,
                        "consequence_terms": ["synonymous_variant"],
                    },
                    "joint": _joint(999, 10000, 0, {"nfe": (999, 8000, 0)}),
                },
            ],
            "clinvar_variants": [
                {
                    "variant_id": "7-2-C-G",
                    "clinical_significance": "Pathogenic",
                    "review_status": "criteria provided, multiple submitters",
                    "gold_stars": 2,
                },
            ],
        }
    }


class _FakeClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []
        # Records the variant_ids passed to each batched submissions call. A single
        # entry means one batched request was made (not one-per-variant).
        self.batch_calls: list[list[str]] = []
        self.submissions: dict[str, list[dict[str, Any]]] = {}

    async def get_gene_carrier_variants(
        self,
        *,
        gene_id: str | None = None,
        gene_symbol: str | None = None,
        dataset: str = "gnomad_r4",
    ) -> dict[str, Any]:
        self.calls.append({"gene_id": gene_id, "gene_symbol": gene_symbol, "dataset": dataset})
        return self.payload

    async def get_clinvar_submissions_batch(
        self, variant_ids: list[str], reference_genome: str = "GRCh38"
    ) -> dict[str, list[dict[str, Any]]]:
        self.batch_calls.append(list(variant_ids))
        return {vid: self.submissions.get(vid, []) for vid in variant_ids}


@pytest.mark.asyncio
async def test_gene_carrier_default_hom_exclusion_golden() -> None:
    client = _FakeClient(_gene_payload())
    svc = GeneCarrierService(client=client)

    result = await svc.get_gene_carrier_frequency(
        gene_symbol="CFTR",
        dataset="gnomad_r4",
        filter_config=FilterConfig(),
        method="hom_exclusion",
    )

    assert result["gene"]["symbol"] == "CFTR"
    assert result["qualifying_count"] == 2  # LoF HC + missense-with-P; synonymous excluded
    # Global GCR = 1 - (1-0.02)(1-0.008) = 0.02784
    assert result["global"]["carrier_frequency"] == pytest.approx(0.02784, abs=1e-9)
    assert result["global"]["sum_af"] == pytest.approx(0.015, abs=1e-12)
    assert result["global"]["genetic_prevalence"] == pytest.approx(0.000225, abs=1e-12)
    # nfe: V1(80/8000) VCR 0.02 ; V2(50/8000,hom5) VCR=(50-10)/4000=0.01 ; GCR=1-(0.98)(0.99)=0.0298
    assert result["populations"]["nfe"]["carrier_frequency"] == pytest.approx(0.0298, abs=1e-9)
    # afr: only V1 -> GCR 0.02
    assert result["populations"]["afr"]["carrier_frequency"] == pytest.approx(0.02, abs=1e-9)
    # source classification
    assert result["sources"]["plof_only"] == 1
    assert result["sources"]["clinvar_only"] == 1


@pytest.mark.asyncio
async def test_gene_carrier_lof_disabled_drops_lof_variant() -> None:
    client = _FakeClient(_gene_payload())
    svc = GeneCarrierService(client=client)

    result = await svc.get_gene_carrier_frequency(
        gene_symbol="CFTR",
        dataset="gnomad_r4",
        filter_config=FilterConfig(lof_hc_enabled=False),
        method="hom_exclusion",
    )
    # Only the missense+ClinVar variant remains.
    assert result["qualifying_count"] == 1
    assert result["global"]["sum_af"] == pytest.approx(0.005, abs=1e-12)


@pytest.mark.asyncio
async def test_gene_carrier_not_found_raises() -> None:
    from gnomad_link.api.base_client import DataNotFoundError

    client = _FakeClient({"gene": None})
    svc = GeneCarrierService(client=client)
    with pytest.raises(DataNotFoundError):
        await svc.get_gene_carrier_frequency(gene_symbol="NOPE", dataset="gnomad_r4")


@pytest.mark.asyncio
async def test_conflicting_resolution_is_batched_and_ac_filtered() -> None:
    """include_conflicting must resolve in ONE batched call (not per-variant), and
    must skip AC<=0 conflicting variants (which can never contribute)."""
    payload = _gene_payload()
    # A conflicting missense with AC>0 and a majority of P/LP submissions -> qualifies.
    payload["gene"]["variants"].append(
        {
            "variant_id": "7-4-A-G",
            "transcript_consequence": {
                "is_canonical": True,
                "lof": None,
                "consequence_terms": ["missense_variant"],
            },
            "joint": _joint(30, 10000, 0, {"nfe": (30, 8000, 0)}),
        }
    )
    # A conflicting missense with AC==0 -> must be filtered out before the batch.
    payload["gene"]["variants"].append(
        {
            "variant_id": "7-5-A-G",
            "transcript_consequence": {
                "is_canonical": True,
                "lof": None,
                "consequence_terms": ["missense_variant"],
            },
            "joint": _joint(0, 10000, 0, {"nfe": (0, 8000, 0)}),
        }
    )
    payload["gene"]["clinvar_variants"].extend(
        [
            {
                "variant_id": "7-4-A-G",
                "clinical_significance": "Conflicting interpretations of pathogenicity",
                "gold_stars": 1,
            },
            {
                "variant_id": "7-5-A-G",
                "clinical_significance": "Conflicting interpretations of pathogenicity",
                "gold_stars": 1,
            },
        ]
    )
    client = _FakeClient(payload)
    client.submissions = {
        "7-4-A-G": [
            {"clinical_significance": "Pathogenic"},
            {"clinical_significance": "Likely pathogenic"},
        ]
    }
    svc = GeneCarrierService(client=client)

    result = await svc.get_gene_carrier_frequency(
        gene_symbol="CFTR",
        dataset="gnomad_r4",
        filter_config=FilterConfig(include_conflicting=True),
    )

    # Exactly ONE batched submissions request, carrying only the AC>0 conflicting id.
    assert len(client.batch_calls) == 1
    assert client.batch_calls[0] == ["7-4-A-G"]
    qualifying_ids = {v["variant_id"] for v in result["qualifying_variants"]}
    assert "7-4-A-G" in qualifying_ids  # resolved P/LP majority -> qualifies
    assert "7-5-A-G" not in qualifying_ids  # AC==0 never qualifies


@pytest.mark.asyncio
async def test_gene_carrier_exclude_high_af_drops_variant() -> None:
    payload = _gene_payload()
    # Bump the LoF variant to AF 0.06 (> BA1 0.05) globally.
    payload["gene"]["variants"][0]["joint"] = _joint(
        700, 10000, 0, {"nfe": (560, 8000, 0), "afr": (140, 2000, 0)}
    )
    client = _FakeClient(payload)
    svc = GeneCarrierService(client=client)

    result = await svc.get_gene_carrier_frequency(
        gene_symbol="CFTR",
        dataset="gnomad_r4",
        filter_config=FilterConfig(),
        method="hom_exclusion",
        exclude_high_af=True,
    )
    # High-AF LoF variant excluded -> only missense remains.
    assert result["qualifying_count"] == 1
    assert result["global"]["sum_af"] == pytest.approx(0.005, abs=1e-12)
