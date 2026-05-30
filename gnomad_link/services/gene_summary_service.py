"""Orchestration service for the get_gene_summary MCP tool.

Assembles a one-shot gene dossier from a single gene_summary GraphQL query:
identity + coordinates, gnomAD constraint, canonical transcript, MANE-Select
transcript, ClinVar variants, and a pext scaffold. The ClinVar block is
best-effort: a malformed upstream shape degrades to an empty list with a
partial flag rather than failing the whole call. Expression (mean pext + top
GTEx tissues) is sourced from the dossier's own build: gnomAD populates
``gene.pext`` and ``gene.transcripts[].gtex_tissue_expression`` on GRCh38, so
the expression fetch stays on the same build (Task C4.3). The GTEx fetch is
itself best-effort, so mean pext survives even when GTEx is unavailable.
"""

from __future__ import annotations

from typing import Any, Protocol

from gnomad_link.mcp.gene_summary_shaping import compact_expression


class _GeneSummaryClient(Protocol):
    async def get_gene_summary(
        self,
        *,
        gene_id: str | None,
        gene_symbol: str | None,
        reference_genome: str,
        dataset: str,
    ) -> dict[str, Any]: ...

    async def get_gene_gtex(
        self,
        *,
        gene_id: str | None = None,
        gene_symbol: str | None = None,
        reference_genome: str = "GRCh38",
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
        include_expression: bool = True,
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

        if include_expression:
            try:
                result["expression"] = await self._fetch_expression(
                    gene=gene,
                    gene_id=gene.get("gene_id") or gene_id,
                    gene_symbol=gene_symbol,
                    dataset=dataset,
                    reference_genome=reference_genome,
                )
            except Exception:
                # Best-effort: never fail the whole call on an expression error.
                result["expression"] = {
                    "unavailable": True,
                    "note": "Expression lookup failed upstream; gene data above is unaffected.",
                }
                result["partial"] = True

        return result

    async def _fetch_expression(
        self,
        *,
        gene: dict[str, Any],
        gene_id: str | None,
        gene_symbol: str | None,
        dataset: str,
        reference_genome: str,
    ) -> dict[str, Any]:
        """Resolve mean pext + canonical-transcript GTEx on the dossier's build.

        ``gene.pext`` (already on the primary gene) and
        ``gene.transcripts[].gtex_tissue_expression`` are both populated on
        GRCh38, so expression stays on ``reference_genome`` with no GRCh37 hop.
        The GTEx fetch is best-effort: a failure leaves mean pext intact rather
        than degrading the whole expression block to unavailable.
        """
        pext = gene.get("pext")
        mane = (gene.get("mane_select_transcript") or {}).get("ensembl_id")
        canonical_id = gene.get("canonical_transcript_id")
        gtex = await self._canonical_gtex(
            gene_id=gene_id,
            gene_symbol=gene_symbol,
            reference_genome=reference_genome,
            target_id=mane or canonical_id,
        )
        return compact_expression(
            pext=pext, gtex_tissue_expression=gtex, source_build=reference_genome
        )

    async def _canonical_gtex(
        self,
        *,
        gene_id: str | None,
        gene_symbol: str | None,
        reference_genome: str,
        target_id: str | None,
    ) -> list[dict[str, Any]]:
        """Best-effort canonical/MANE-transcript GTEx from gene.transcripts.

        Returns [] on any upstream error so mean pext is preserved.
        """
        try:
            raw = await self.client.get_gene_gtex(
                gene_id=gene_id,
                gene_symbol=gene_symbol,
                reference_genome=reference_genome,
            )
        except Exception:
            return []
        transcripts = (raw.get("gene") or {}).get("transcripts") or []
        if target_id:
            for transcript in transcripts:
                if transcript.get("transcript_id") == target_id:
                    return list(transcript.get("gtex_tissue_expression") or [])
        # Fall back to the first transcript that carries GTEx values.
        for transcript in transcripts:
            gtex = transcript.get("gtex_tissue_expression")
            if gtex:
                return list(gtex)
        return []
