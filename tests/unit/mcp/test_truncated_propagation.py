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


def test_compact_keeps_canonical_transcript_first() -> None:
    from gnomad_link.mcp.shaping import shape_variant_details_compact

    raw: dict[str, Any] = {
        "variant_id": "1-55051215-G-GA",
        "transcript_consequences": [
            {"transcript_id": "ENST00000000001", "biotype": "protein_coding"},
            {"transcript_id": "ENST00000000002", "biotype": "nonsense_mediated_decay"},
            {
                "transcript_id": "ENST00000000003",
                "biotype": "protein_coding",
                "canonical": True,
            },
            {
                "transcript_id": "ENST00000000004",
                "biotype": "protein_coding",
                "mane_select": "NM_xxx",
            },
            {"transcript_id": "ENST00000000005", "biotype": "protein_coding"},
        ],
    }

    result = shape_variant_details_compact(raw, max_transcripts=2)

    kept_ids = [tx["transcript_id"] for tx in result["transcript_consequences"]]
    assert kept_ids == ["ENST00000000003", "ENST00000000004"]


def test_compact_falls_back_to_first_protein_coding() -> None:
    from gnomad_link.mcp.shaping import shape_variant_details_compact

    raw: dict[str, Any] = {
        "variant_id": "1-55051215-G-GA",
        "transcript_consequences": [
            {"transcript_id": "ENST00000000001", "biotype": "nonsense_mediated_decay"},
            {"transcript_id": "ENST00000000002", "biotype": "protein_coding"},
            {"transcript_id": "ENST00000000003", "biotype": "retained_intron"},
            {"transcript_id": "ENST00000000004", "biotype": "protein_coding"},
        ],
    }

    result = shape_variant_details_compact(raw, max_transcripts=2)

    kept_ids = [tx["transcript_id"] for tx in result["transcript_consequences"]]
    assert kept_ids == ["ENST00000000002", "ENST00000000004"]


def test_compact_falls_back_to_original_order_for_other_biotypes() -> None:
    from gnomad_link.mcp.shaping import shape_variant_details_compact

    raw: dict[str, Any] = {
        "variant_id": "1-55051215-G-GA",
        "transcript_consequences": [
            {"transcript_id": "ENST00000000001", "biotype": "lincRNA"},
            {"transcript_id": "ENST00000000002", "biotype": "lincRNA"},
            {"transcript_id": "ENST00000000003", "biotype": "lincRNA"},
        ],
    }

    result = shape_variant_details_compact(raw, max_transcripts=2)

    kept_ids = [tx["transcript_id"] for tx in result["transcript_consequences"]]
    assert kept_ids == ["ENST00000000001", "ENST00000000002"]
