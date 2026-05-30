from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.services.gene_summary_service import GeneSummaryService


class _FakeClient:
    def __init__(self, gene_payload: dict[str, Any]) -> None:
        self.gene_payload = gene_payload
        self.calls: list[dict[str, Any]] = []

    async def get_gene_summary(
        self,
        *,
        gene_id: str | None,
        gene_symbol: str | None,
        reference_genome: str,
        dataset: str,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "gene_id": gene_id,
                "gene_symbol": gene_symbol,
                "reference_genome": reference_genome,
                "dataset": dataset,
            }
        )
        return {"gene": self.gene_payload}


def _gene_payload() -> dict[str, Any]:
    return {
        "gene_id": "ENSG00000169174",
        "symbol": "PCSK9",
        "name": "proprotein convertase subtilisin/kexin type 9",
        "chrom": "1",
        "start": 55039447,
        "stop": 55064852,
        "canonical_transcript_id": "ENST00000302118",
        "gnomad_constraint": {"pli": 0.01, "oe_lof": 0.8, "mis_z": 1.2},
        "mane_select_transcript": {
            "ensembl_id": "ENST00000302118",
            "ensembl_version": "5",
            "refseq_id": "NM_174936",
            "refseq_version": "4",
        },
        "clinvar_variants": [
            {
                "variant_id": "1-55039974-G-T",
                "clinical_significance": "Pathogenic",
                "gold_stars": 2,
            },
        ],
        "pext": {"flags": [], "regions": []},
    }


@pytest.mark.asyncio
async def test_get_gene_summary_returns_gene_block_on_dataset_genome() -> None:
    client = _FakeClient(_gene_payload())
    svc = GeneSummaryService(client=client)

    result = await svc.get_gene_summary(
        gene_id="ENSG00000169174",
        gene_symbol=None,
        dataset="gnomad_r4",
    )

    assert result["gene_id"] == "ENSG00000169174"
    assert result["symbol"] == "PCSK9"
    assert result["coords"] == {"chrom": "1", "start": 55039447, "stop": 55064852}
    assert result["dataset"] == "gnomad_r4"
    assert result["constraint"]["pli"] == 0.01
    assert result["canonical_transcript_id"] == "ENST00000302118"
    assert result["mane_select_transcript"]["refseq_id"] == "NM_174936"
    assert result["clinvar_variants"][0]["variant_id"] == "1-55039974-G-T"
    # gnomad_r4 -> GRCh38 reference genome for the primary fetch.
    assert client.calls[0]["reference_genome"] == "GRCh38"


@pytest.mark.asyncio
async def test_get_gene_summary_uses_grch37_for_r2_1_dataset() -> None:
    client = _FakeClient(_gene_payload())
    svc = GeneSummaryService(client=client)

    await svc.get_gene_summary(gene_id="ENSG00000169174", gene_symbol=None, dataset="gnomad_r2_1")

    assert client.calls[0]["reference_genome"] == "GRCh37"


@pytest.mark.asyncio
async def test_get_gene_summary_clinvar_failure_sets_partial_flag() -> None:
    payload = _gene_payload()
    # A clinvar_variants value the shaper cannot iterate triggers the best-effort guard.
    payload["clinvar_variants"] = {"unexpected": "shape"}
    client = _FakeClient(payload)
    svc = GeneSummaryService(client=client)

    result = await svc.get_gene_summary(
        gene_id="ENSG00000169174", gene_symbol=None, dataset="gnomad_r4"
    )

    assert result["partial"] is True
    assert result["clinvar_variants"] == []


class _ExpressionClient:
    """Captures the GRCh37 fallback fetch and returns canned pext / GTEx."""

    def __init__(
        self,
        primary: dict[str, Any],
        grch37: dict[str, Any] | None = None,
        gtex: list[dict[str, Any]] | None = None,
        raise_grch37: bool = False,
    ) -> None:
        self.primary = primary
        self.grch37 = grch37
        self.gtex = gtex
        self.raise_grch37 = raise_grch37
        self.gene_calls: list[str] = []
        self.transcript_calls: list[tuple[str, str]] = []

    async def get_gene_summary(
        self,
        *,
        gene_id: str | None,
        gene_symbol: str | None,
        reference_genome: str,
        dataset: str,
    ) -> dict[str, Any]:
        self.gene_calls.append(reference_genome)
        if reference_genome == "GRCh37":
            if self.raise_grch37:
                raise RuntimeError("upstream GRCh37 fetch failed")
            return {"gene": self.grch37}
        return {"gene": self.primary}

    async def get_transcript_gtex(
        self, transcript_id: str, reference_genome: str = "GRCh37"
    ) -> dict[str, Any]:
        self.transcript_calls.append((transcript_id, reference_genome))
        return {"transcript": {"gtex_tissue_expression": self.gtex or []}}


def _grch37_gene_with_pext() -> dict[str, Any]:
    g = _gene_payload()
    g["pext"] = {"flags": [], "regions": [{"start": 1, "stop": 10, "mean": 0.9}]}
    return g


@pytest.mark.asyncio
async def test_expression_fetched_from_grch37_when_dataset_is_grch38() -> None:
    primary = _gene_payload()  # GRCh38 -> empty pext
    client = _ExpressionClient(
        primary=primary,
        grch37=_grch37_gene_with_pext(),
        gtex=[{"tissue": "Liver", "value": 42.0}],
    )
    svc = GeneSummaryService(client=client)

    result = await svc.get_gene_summary(
        gene_id="ENSG00000169174", gene_symbol=None, dataset="gnomad_r4", include_expression=True
    )

    assert client.gene_calls == ["GRCh38", "GRCh37"]
    assert result["expression"]["source_build"] == "GRCh37"
    assert result["expression"]["mean_pext"] == 0.9
    assert result["expression"]["top_tissues"][0]["tissue"] == "Liver"


@pytest.mark.asyncio
async def test_expression_skipped_when_include_expression_false() -> None:
    client = _ExpressionClient(primary=_gene_payload())
    svc = GeneSummaryService(client=client)

    result = await svc.get_gene_summary(
        gene_id="ENSG00000169174", gene_symbol=None, dataset="gnomad_r4", include_expression=False
    )

    assert client.gene_calls == ["GRCh38"]
    assert "expression" not in result


@pytest.mark.asyncio
async def test_expression_failure_degrades_to_unavailable_and_sets_partial() -> None:
    client = _ExpressionClient(primary=_gene_payload(), raise_grch37=True)
    svc = GeneSummaryService(client=client)

    result = await svc.get_gene_summary(
        gene_id="ENSG00000169174", gene_symbol=None, dataset="gnomad_r4", include_expression=True
    )

    assert result["expression"]["unavailable"] is True
    assert result["partial"] is True
