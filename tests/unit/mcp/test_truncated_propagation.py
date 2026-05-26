"""Tests for self-describing truncated blocks across heavy-payload tools.

The pattern (truncated.kind, dropped, to_disable, to_restore) already exists
for shape_variant_frequencies and shape_gene_variants. This module pins the
same contract for variant_details (transcript caps), gene_details (heavy
arrays), and clinvar submissions.
"""

from __future__ import annotations

from typing import Any


def test_variant_details_compact_emits_truncated_when_transcripts_dropped() -> None:
    from gnomad_link.mcp.shaping import shape_variant_details_compact

    transcripts = [
        {"transcript_id": f"ENST{i:011d}", "biotype": "protein_coding"} for i in range(50)
    ]
    raw: dict[str, Any] = {
        "variant_id": "1-55051215-G-GA",
        "transcript_consequences": transcripts,
    }

    result = shape_variant_details_compact(raw, max_transcripts=10)

    assert len(result["transcript_consequences"]) == 10
    trunc = result["truncated"]
    assert trunc["kind"] == "transcript_consequences"
    assert trunc["dropped"] == 40
    assert trunc["to_restore"] == "response_mode='full'"


def test_gene_details_compact_emits_truncated_when_present() -> None:
    from gnomad_link.mcp.shaping import shape_gene_details_compact

    raw: dict[str, Any] = {
        "gene_id": "ENSG00000169174",
        "symbol": "PCSK9",
        "transcripts": [{"transcript_id": "x"}, {"transcript_id": "y"}],
        "exons": [{"start": 1, "stop": 100}],
    }

    result = shape_gene_details_compact(raw)

    assert "transcripts" not in result
    assert "exons" not in result
    trunc = result["truncated"]
    assert trunc["kind"] == "gene_payload"
    assert trunc["dropped"] == {"transcripts": 2, "exons": 1}
    assert trunc["to_restore"] == "response_mode='full'"


def test_clinvar_submissions_emit_truncated_when_capped() -> None:
    from gnomad_link.mcp.shaping import shape_clinvar_submissions

    payload: dict[str, Any] = {"submissions": [{"id": i} for i in range(30)]}

    result = shape_clinvar_submissions(payload, submissions_limit=5)

    assert len(result["submissions"]) == 5
    trunc = result["truncated"]
    assert trunc["kind"] == "submissions"
    assert trunc["dropped"] == 25
    assert trunc["to_disable"] == "raise submissions_limit (max 200)"
    assert trunc["to_restore"] == "submissions_limit=30"
