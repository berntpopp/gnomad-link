from __future__ import annotations

import pytest


def test_region_model_roundtrip() -> None:
    from gnomad_link.models.region_models import Region

    payload = {
        "chrom": "17",
        "start": 7674232,
        "stop": 7674252,
        "reference_genome": "GRCh38",
        "genes": [
            {"gene_id": "ENSG00000141510", "symbol": "TP53", "start": 7661779, "stop": 7687538}
        ],
        "clinvar_variants": [
            {
                "variant_id": "17-7674232-C-G",
                "clinical_significance": "Pathogenic",
                "gold_stars": 2,
                "major_consequence": "missense_variant",
                "pos": 7674232,
                "review_status": "criteria provided, multiple submitters, no conflicts",
            }
        ],
    }
    region = Region.model_validate(payload)
    assert region.chrom == "17"
    assert region.genes[0].symbol == "TP53"


def test_transcript_model_roundtrip() -> None:
    from gnomad_link.models.transcript_models import Transcript

    payload = {
        "transcript_id": "ENST00000302118",
        "gene_id": "ENSG00000169174",
        "gene_symbol": "PCSK9",
        "chrom": "1",
        "start": 55039549,
        "stop": 55064852,
        "strand": "+",
        "reference_genome": "GRCh38",
        "exons": [{"feature_type": "CDS", "start": 55039549, "stop": 55039750}],
    }
    transcript = Transcript.model_validate(payload)
    assert transcript.gene_symbol == "PCSK9"
    assert transcript.exons[0].feature_type == "CDS"


def test_variant_details_accepts_unknown_fields() -> None:
    """gnomAD adds fields over time; variant details must not reject upstream growth."""

    from gnomad_link.models.variant_models import VariantDetails

    payload = {
        "variant_id": "1-55051215-G-GA",
        "reference_genome": "GRCh38",
        "pos": 55051215,
        "ref": "G",
        "alt": "GA",
        "rsids": ["rs11591147"],
        "future_field_we_dont_know": {"surprise": True},
    }
    details = VariantDetails.model_validate(payload)
    assert details.variant_id == "1-55051215-G-GA"


def test_variant_search_result_model() -> None:
    from gnomad_link.models.variant_models import VariantSearchResult

    result = VariantSearchResult.model_validate({"variant_id": "1-55051215-G-GA"})
    assert result.variant_id == "1-55051215-G-GA"
