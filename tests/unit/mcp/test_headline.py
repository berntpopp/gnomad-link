"""Plain-English headline builders: accurate rendering + null-safety.

A headline must never raise (it is attached unconditionally) and must read like
a sentence an LLM can hand back to the user.
"""

from __future__ import annotations

from gnomad_link.mcp.headline import (
    gene_carrier_headline,
    gene_details_headline,
    variant_carrier_headline,
    variant_frequencies_headline,
)


def test_gene_carrier_headline_matches_reviewer_format() -> None:
    shaped = {
        "gene": {"gene_id": "ENSG1", "symbol": "CFTR"},
        "dataset": "gnomad_r4",
        "global": {"carrier_one_in": 18},
        "populations": [
            {"population": "asj", "carrier_one_in": 9},
            {"population": "nfe", "carrier_one_in": 16},
        ],
        "contributing_variants": {"count": 523},
    }
    headline = gene_carrier_headline(shaped)
    assert headline == (
        "CFTR (gnomad_r4): carrier frequency 1 in 18 globally; "
        "highest 1 in 9 (asj); 523 qualifying variants. Research use only."
    )


def test_gene_carrier_headline_null_safe_when_empty() -> None:
    headline = gene_carrier_headline({})
    assert "carrier frequency unavailable globally" in headline
    assert headline.endswith("Research use only.")


def test_variant_carrier_headline_ar_with_ci() -> None:
    result = {
        "variant_id": "7-117559590-ATCT-A",
        "inheritance": "AR",
        "dataset": "gnomad_r4",
        "method": "hwe",
        "overall": {"carrier_frequency": 0.0449, "ci_low": 0.0410, "ci_high": 0.0490},
        "summary": {"max_carrier_frequency_population": "nfe"},
    }
    headline = variant_carrier_headline(result)
    assert headline.startswith("7-117559590-ATCT-A (AR/gnomad_r4): carrier frequency 0.045")
    assert "95% CI" in headline
    assert "highest in nfe" in headline
    assert headline.endswith("method=hwe")


def test_variant_carrier_headline_ad_and_xl_variants() -> None:
    ad = variant_carrier_headline(
        {
            "variant_id": "1-1-A-T",
            "inheritance": "AD",
            "dataset": "gnomad_r4",
            "overall": {"affected_or_carrier_frequency": 0.002},
        }
    )
    assert "affected-or-carrier frequency" in ad
    xl = variant_carrier_headline(
        {
            "variant_id": "X-1-A-T",
            "inheritance": "XL",
            "dataset": "gnomad_r4",
            "overall": {"female_carrier_frequency": 0.01, "affected_male_frequency": 0.005},
        }
    )
    assert "female carrier frequency" in xl and "affected male frequency" in xl


def test_variant_carrier_headline_missing_overall_is_safe() -> None:
    headline = variant_carrier_headline(
        {"variant_id": "1-1-A-T", "inheritance": "AR", "dataset": "gnomad_r4"}
    )
    assert "carrier frequency unavailable" in headline


def test_variant_frequencies_headline_renders_summary() -> None:
    payload = {
        "variant_id": "1-55051215-G-GA",
        "dataset": "gnomad_r4",
        "major_consequence": "missense_variant",
        "summary": {"overall_af": 0.00023, "max_pop": "nfe", "max_pop_af": 0.00045},
    }
    headline = variant_frequencies_headline(payload)
    assert headline.startswith("1-55051215-G-GA missense_variant: AF 0.00023 in gnomad_r4")
    assert "highest in nfe" in headline


def test_variant_frequencies_headline_no_data() -> None:
    headline = variant_frequencies_headline({"variant_id": "1-1-A-T", "dataset": "gnomad_r4"})
    assert headline == "1-1-A-T (gnomad_r4): no allele-frequency data."


def test_gene_details_headline_with_constraint_and_coords() -> None:
    result = {
        "symbol": "PCSK9",
        "gene_id": "ENSG00000169174",
        "gnomad_constraint": {"pli": 0.0042, "oe_lof": 0.83},
        "chrom": "1",
        "start": 55039447,
        "stop": 55064852,
    }
    headline = gene_details_headline(result, reference_genome="GRCh38")
    assert headline == (
        "PCSK9 (ENSG00000169174): pLI 0.004, LoF o/e 0.83; 1:55039447-55064852 (GRCh38)."
    )


def test_gene_details_headline_missing_constraint_is_safe() -> None:
    headline = gene_details_headline(
        {"symbol": "FOO", "gene_id": "ENSG9", "chrom": "2", "start": 1, "stop": 2},
        reference_genome="GRCh38",
    )
    assert "constraint unavailable" in headline
    assert "2:1-2 (GRCh38)" in headline
