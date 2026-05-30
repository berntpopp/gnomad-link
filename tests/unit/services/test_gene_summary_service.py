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
        # GRCh38 pext IS populated (verified live against gnomAD r4).
        "pext": {"flags": [], "regions": [{"start": 1, "stop": 10, "mean": 0.9}]},
    }


@pytest.mark.asyncio
async def test_get_gene_summary_returns_gene_block_on_dataset_genome() -> None:
    client = _FakeClient(_gene_payload())
    svc = GeneSummaryService(client=client)

    result = await svc.get_gene_summary(
        gene_id="ENSG00000169174",
        gene_symbol=None,
        dataset="gnomad_r4",
        include_expression=False,
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

    await svc.get_gene_summary(
        gene_id="ENSG00000169174",
        gene_symbol=None,
        dataset="gnomad_r2_1",
        include_expression=False,
    )

    assert client.calls[0]["reference_genome"] == "GRCh37"


@pytest.mark.asyncio
async def test_get_gene_summary_clinvar_failure_sets_partial_flag() -> None:
    payload = _gene_payload()
    # A clinvar_variants value the shaper cannot iterate triggers the best-effort guard.
    payload["clinvar_variants"] = {"unexpected": "shape"}
    client = _FakeClient(payload)
    svc = GeneSummaryService(client=client)

    result = await svc.get_gene_summary(
        gene_id="ENSG00000169174",
        gene_symbol=None,
        dataset="gnomad_r4",
        include_expression=False,
    )

    assert result["partial"] is True
    assert result["clinvar_variants"] == []


class _ExpressionClient:
    """Primary gene fetch + the gene.transcripts GTEx fetch (GRCh38 path)."""

    def __init__(
        self,
        primary: dict[str, Any],
        gtex_gene: dict[str, Any] | None = None,
        raise_gtex: bool = False,
    ) -> None:
        self.primary = primary
        self.gtex_gene = gtex_gene
        self.raise_gtex = raise_gtex
        self.gene_calls: list[str] = []
        self.gtex_calls: list[str] = []

    async def get_gene_summary(
        self,
        *,
        gene_id: str | None,
        gene_symbol: str | None,
        reference_genome: str,
        dataset: str,
    ) -> dict[str, Any]:
        self.gene_calls.append(reference_genome)
        return {"gene": self.primary}

    async def get_gene_gtex(
        self,
        *,
        gene_id: str | None = None,
        gene_symbol: str | None = None,
        reference_genome: str = "GRCh38",
    ) -> dict[str, Any]:
        self.gtex_calls.append(reference_genome)
        if self.raise_gtex:
            raise RuntimeError("upstream GTEx fetch failed")
        return {"gene": self.gtex_gene or {}}


def _gtex_gene(canonical: str = "ENST00000302118") -> dict[str, Any]:
    return {
        "canonical_transcript_id": canonical,
        "mane_select_transcript": {"ensembl_id": canonical},
        "transcripts": [
            {
                "transcript_id": "ENST00000999999",
                "gtex_tissue_expression": [{"tissue": "Brain", "value": 1.0}],
            },
            {
                "transcript_id": canonical,
                "gtex_tissue_expression": [
                    {"tissue": "Liver", "value": 42.0},
                    {"tissue": "Adipose", "value": 5.0},
                ],
            },
        ],
    }


@pytest.mark.asyncio
async def test_expression_sourced_from_grch38_gene_transcripts() -> None:
    # GRCh38 primary gene already carries pext; GTEx comes from gene.transcripts
    # on the SAME build (no GRCh37 hop).
    client = _ExpressionClient(primary=_gene_payload(), gtex_gene=_gtex_gene())
    svc = GeneSummaryService(client=client)

    result = await svc.get_gene_summary(
        gene_id="ENSG00000169174", gene_symbol=None, dataset="gnomad_r4", include_expression=True
    )

    expr = result["expression"]
    assert expr["source_build"] == "GRCh38"
    assert expr["mean_pext"] == 0.9
    # GTEx is pulled from the MANE/canonical transcript, not the first transcript.
    assert expr["top_tissues"][0] == {"tissue": "Liver", "value": 42.0}
    # No GRCh37 backfill: the primary summary is fetched once on GRCh38; GTEx on GRCh38.
    assert client.gene_calls == ["GRCh38"]
    assert client.gtex_calls == ["GRCh38"]


@pytest.mark.asyncio
async def test_expression_gtex_best_effort_keeps_mean_pext() -> None:
    # GTEx fetch failing must NOT wipe mean_pext (still available from gene.pext).
    client = _ExpressionClient(primary=_gene_payload(), raise_gtex=True)
    svc = GeneSummaryService(client=client)

    result = await svc.get_gene_summary(
        gene_id="ENSG00000169174", gene_symbol=None, dataset="gnomad_r4", include_expression=True
    )

    expr = result["expression"]
    assert expr.get("unavailable") is not True
    assert expr["mean_pext"] == 0.9
    assert expr["top_tissues"] == []


@pytest.mark.asyncio
async def test_expression_unavailable_when_no_pext_and_no_gtex() -> None:
    primary = _gene_payload()
    primary["pext"] = {"flags": [], "regions": []}  # truly empty
    client = _ExpressionClient(primary=primary, raise_gtex=True)
    svc = GeneSummaryService(client=client)

    result = await svc.get_gene_summary(
        gene_id="ENSG00000169174", gene_symbol=None, dataset="gnomad_r4", include_expression=True
    )

    assert result["expression"]["unavailable"] is True


@pytest.mark.asyncio
async def test_expression_skipped_when_include_expression_false() -> None:
    client = _ExpressionClient(primary=_gene_payload())
    svc = GeneSummaryService(client=client)

    result = await svc.get_gene_summary(
        gene_id="ENSG00000169174", gene_symbol=None, dataset="gnomad_r4", include_expression=False
    )

    assert client.gene_calls == ["GRCh38"]
    assert client.gtex_calls == []
    assert "expression" not in result
