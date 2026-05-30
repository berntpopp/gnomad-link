"""Orchestration service for the get_gene_summary MCP tool.

Assembles a one-shot gene dossier from a single gene_summary GraphQL query:
identity + coordinates, gnomAD constraint, canonical transcript, MANE-Select
transcript, ClinVar variants, and a pext scaffold. The ClinVar block is
best-effort: a malformed upstream shape degrades to an empty list with a
partial flag rather than failing the whole call. Expression (pext + GTEx) is
populated on GRCh37 and typically empty on GRCh38; the GRCh37 best-effort
expression fetch lands in Task C4.3.
"""

from __future__ import annotations

from typing import Any, Protocol


class _GeneSummaryClient(Protocol):
    async def get_gene_summary(
        self,
        *,
        gene_id: str | None,
        gene_symbol: str | None,
        reference_genome: str,
        dataset: str,
    ) -> dict[str, Any]: ...


def _dataset_reference_genome(dataset: str) -> str:
    """gnomad_r2_1 is GRCh37; gnomad_r3 / gnomad_r4 are GRCh38."""
    return "GRCh37" if dataset == "gnomad_r2_1" else "GRCh38"


class GeneSummaryService:
    """Assemble the gene_summary dossier from the unified gnomAD client."""

    def __init__(self, client: _GeneSummaryClient) -> None:
        self.client = client

    async def get_gene_summary(
        self,
        *,
        gene_id: str | None,
        gene_symbol: str | None,
        dataset: str = "gnomad_r4",
    ) -> dict[str, Any]:
        reference_genome = _dataset_reference_genome(dataset)
        raw = await self.client.get_gene_summary(
            gene_id=gene_id,
            gene_symbol=gene_symbol,
            reference_genome=reference_genome,
            dataset=dataset,
        )
        gene = raw.get("gene")
        if not gene:
            from gnomad_link.api.base_client import DataNotFoundError

            raise DataNotFoundError(
                f"Gene not found: gene_id={gene_id} gene_symbol={gene_symbol} in {dataset}"
            )

        partial = False
        raw_clinvar = gene.get("clinvar_variants")
        if isinstance(raw_clinvar, list):
            clinvar_variants = raw_clinvar
        else:
            clinvar_variants = []
            if raw_clinvar is not None:
                partial = True

        result: dict[str, Any] = {
            "gene_id": gene.get("gene_id"),
            "symbol": gene.get("symbol"),
            "name": gene.get("name"),
            "coords": {
                "chrom": gene.get("chrom"),
                "start": gene.get("start"),
                "stop": gene.get("stop"),
            },
            "dataset": dataset,
            "reference_genome": reference_genome,
            "constraint": gene.get("gnomad_constraint"),
            "canonical_transcript_id": gene.get("canonical_transcript_id"),
            "mane_select_transcript": gene.get("mane_select_transcript"),
            "clinvar_variants": clinvar_variants,
            "pext": gene.get("pext"),
            "flags": gene.get("flags") or [],
            "partial": partial,
        }
        return result
