"""M-4: get_transcript_details delivers GTEx via the gene path + unwraps payload."""

from __future__ import annotations

from typing import Any

import pytest

_TRANSCRIPT = {
    "transcript_id": "ENST00000302118",
    "gene_id": "ENSG00000169174",
    "reference_genome": "GRCh38",
    "chrom": "1",
    "start": 55039548,
    "stop": 55064852,
    "exons": [{"feature_type": "CDS", "start": 55039838, "stop": 55040044}],
}

_GENE_GTEX = {
    "gene": {
        "transcripts": [
            {
                "transcript_id": "ENST00000302118",
                "gtex_tissue_expression": [
                    {"tissue": "Liver", "value": 90.1},
                    {"tissue": "Whole_Blood", "value": 1.2},
                ],
            },
            {"transcript_id": "ENSTOTHER", "gtex_tissue_expression": [{"tissue": "X", "value": 5}]},
        ]
    }
}


class _FakeClient:
    def __init__(self, *, transcript: Any, gtex: Any = None, gtex_error: bool = False) -> None:
        self._transcript = transcript
        self._gtex = gtex
        self._gtex_error = gtex_error
        self.gtex_calls = 0

    async def get_transcript(
        self, transcript_id: str, reference_genome: str | None = None
    ) -> dict[str, Any]:
        return self._transcript

    async def get_gene_gtex(
        self,
        *,
        gene_id: str | None = None,
        gene_symbol: str | None = None,
        reference_genome: str = "GRCh38",
    ) -> dict[str, Any]:
        self.gtex_calls += 1
        if self._gtex_error:
            raise RuntimeError("gtex upstream failed")
        return self._gtex or {}


@pytest.mark.asyncio
async def test_unwraps_and_attaches_top_tissues() -> None:
    from gnomad_link.services.transcript_service import TranscriptService

    client = _FakeClient(transcript={"transcript": dict(_TRANSCRIPT)}, gtex=_GENE_GTEX)
    result = await TranscriptService(client).get_transcript_details(transcript_id="ENST00000302118")

    # Unwrapped: top-level transcript fields, not a {"transcript": ...} wrapper.
    assert result["transcript_id"] == "ENST00000302118"
    assert "transcript" not in result
    expr = result["expression"]
    assert expr["top_tissues"][0] == {"tissue": "Liver", "value": 90.1}
    assert expr["source_build"] == "GRCh38"
    assert expr["pext_note"] == "pext is gene-level; use get_gene_summary for mean_pext"


@pytest.mark.asyncio
async def test_expression_skipped_when_disabled() -> None:
    from gnomad_link.services.transcript_service import TranscriptService

    client = _FakeClient(transcript={"transcript": dict(_TRANSCRIPT)}, gtex=_GENE_GTEX)
    result = await TranscriptService(client).get_transcript_details(
        transcript_id="ENST00000302118", include_expression=False
    )

    assert "expression" not in result
    assert client.gtex_calls == 0  # no extra upstream call


@pytest.mark.asyncio
async def test_gtex_error_is_best_effort() -> None:
    from gnomad_link.services.transcript_service import TranscriptService

    client = _FakeClient(transcript={"transcript": dict(_TRANSCRIPT)}, gtex_error=True)
    result = await TranscriptService(client).get_transcript_details(transcript_id="ENST00000302118")

    # Exon structure survives; expression degrades gracefully.
    assert result["exons"]
    assert result["expression"]["unavailable"] is True


@pytest.mark.asyncio
async def test_missing_transcript_raises_not_found() -> None:
    from gnomad_link.api.base_client import DataNotFoundError
    from gnomad_link.services.transcript_service import TranscriptService

    client = _FakeClient(transcript={"transcript": None})
    with pytest.raises(DataNotFoundError):
        await TranscriptService(client).get_transcript_details(transcript_id="ENSTMISSING")


@pytest.mark.asyncio
async def test_tool_returns_unwrapped_with_expression() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    class _Stub:
        async def get_transcript_details(
            self,
            *,
            transcript_id: str,
            reference_genome: str = "GRCh38",
            include_expression: bool = True,
        ) -> dict[str, Any]:
            out = dict(_TRANSCRIPT)
            if include_expression:
                out["expression"] = {"source_build": reference_genome, "top_tissues": []}
            return out

    mcp = create_gnomad_mcp(service_factory=lambda: _Stub())
    result = await mcp.call_tool("get_transcript_details", {"transcript_id": "ENST00000302118"})
    payload = result.structured_content or {}

    assert payload.get("transcript_id") == "ENST00000302118"
    assert "transcript" not in payload  # flat, not wrapped
    assert "expression" in payload
