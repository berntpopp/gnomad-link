"""Transcript-detail orchestration: exon structure + best-effort GTEx expression.

The standalone ``transcript().gtex_tissue_expression`` field is unavailable on
GRCh38 and errors upstream on GRCh37, so GTEx is sourced via the working gene
path (``gene.transcripts[].gtex_tissue_expression``), filtered to the requested
transcript. Transcript expression contains tissue rows only; pext is gene-level,
so callers should use get_gene_summary for mean_pext. The GTEx fetch is
best-effort: exon/structure survive a GTEx error.
"""

from __future__ import annotations

from typing import Any, Protocol

from gnomad_link.mcp.gene_summary_shaping import compact_expression


class _TranscriptClient(Protocol):
    async def get_transcript(
        self,
        transcript_id: str,
        reference_genome: str | None = None,
        dataset: str | None = None,
    ) -> dict[str, Any]: ...

    async def get_gene_gtex(
        self,
        *,
        gene_id: str | None = None,
        gene_symbol: str | None = None,
        reference_genome: str = "GRCh38",
    ) -> dict[str, Any]: ...


class TranscriptService:
    """Assemble the transcript dossier from the unified gnomAD client."""

    def __init__(self, client: _TranscriptClient) -> None:
        self.client = client

    async def get_transcript_details(
        self,
        *,
        transcript_id: str,
        reference_genome: str = "GRCh38",
        include_expression: bool = True,
    ) -> dict[str, Any]:
        raw = await self.client.get_transcript(transcript_id, reference_genome)
        # Unwrap the GraphQL {"transcript": {...}} wrapper to a flat payload, and
        # raise rather than return an empty success on a missing transcript.
        transcript = raw.get("transcript", raw) if isinstance(raw, dict) else raw
        if not transcript:
            from gnomad_link.api.base_client import DataNotFoundError

            raise DataNotFoundError(f"Transcript {transcript_id} not found in {reference_genome}")

        result = dict(transcript)
        if include_expression:
            result["expression"] = await self._fetch_expression(transcript, reference_genome)
        return result

    async def _fetch_expression(
        self, transcript: dict[str, Any], reference_genome: str
    ) -> dict[str, Any]:
        gene_id = transcript.get("gene_id") or (transcript.get("gene") or {}).get("gene_id")
        transcript_id = transcript.get("transcript_id")
        if not gene_id:
            return {
                "unavailable": True,
                "note": "No gene_id on the transcript; GTEx expression is unavailable.",
            }
        try:
            raw = await self.client.get_gene_gtex(
                gene_id=gene_id, reference_genome=reference_genome
            )
        except Exception:
            return {
                "unavailable": True,
                "note": "GTEx lookup failed upstream; exon structure above is unaffected.",
            }
        gtex = self._select_transcript_gtex(raw, transcript_id)
        expression = compact_expression(
            pext=None, gtex_tissue_expression=gtex, source_build=reference_genome
        )
        expression["pext_note"] = "pext is gene-level; use get_gene_summary for mean_pext"
        return expression

    @staticmethod
    def _select_transcript_gtex(
        raw: dict[str, Any], transcript_id: str | None
    ) -> list[dict[str, Any]]:
        transcripts = (raw.get("gene") or {}).get("transcripts") or []
        for transcript in transcripts:
            if transcript.get("transcript_id") == transcript_id:
                return list(transcript.get("gtex_tissue_expression") or [])
        return []
