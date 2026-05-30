from __future__ import annotations

from gnomad_link.services.gene_carrier_filters import (
    FilterConfig,
    clinvar_evidence,
    is_genomes_only,
    is_gnomad_filtered,
    is_hc_lof,
    is_high_af,
    is_high_hom,
    is_missense,
    is_pathogenic_clinvar,
    meets_conflicting_threshold,
    qualifies,
)


def _csq(**kw: object) -> dict[str, object]:
    base = {"is_canonical": True, "lof": None, "consequence_terms": []}
    base.update(kw)
    return base


# --- consequence predicates ---


def test_is_hc_lof_requires_canonical_and_hc() -> None:
    assert is_hc_lof(_csq(lof="HC")) is True
    assert is_hc_lof(_csq(lof="LC")) is False
    assert is_hc_lof(_csq(lof="HC", is_canonical=False)) is False
    assert is_hc_lof(None) is False


def test_is_missense_matches_missense_and_inframe_on_canonical() -> None:
    assert is_missense(_csq(consequence_terms=["missense_variant"])) is True
    assert is_missense(_csq(consequence_terms=["inframe_deletion"])) is True
    assert is_missense(_csq(consequence_terms=["synonymous_variant"])) is False
    assert is_missense(_csq(consequence_terms=["missense_variant"], is_canonical=False)) is False


# --- clinvar predicates ---


def test_is_pathogenic_clinvar_space_separated_and_threshold() -> None:
    assert (
        is_pathogenic_clinvar({"clinical_significance": "Pathogenic", "gold_stars": 2}, 2) is True
    )
    assert (
        is_pathogenic_clinvar({"clinical_significance": "Likely pathogenic", "gold_stars": 3}, 2)
        is True
    )
    # below star threshold
    assert (
        is_pathogenic_clinvar({"clinical_significance": "Pathogenic", "gold_stars": 1}, 2) is False
    )
    # conflicting excluded even though it contains "pathogenicity"
    assert (
        is_pathogenic_clinvar(
            {
                "clinical_significance": "Conflicting interpretations of pathogenicity",
                "gold_stars": 3,
            },
            2,
        )
        is False
    )
    assert (
        is_pathogenic_clinvar(
            {"clinical_significance": "Uncertain significance", "gold_stars": 3}, 2
        )
        is False
    )


# --- clinvar_evidence + qualifies decision tree ---


def test_clinvar_evidence_standard_and_conflicting_optin() -> None:
    cfg = FilterConfig()
    path = {"clinical_significance": "Pathogenic", "gold_stars": 2}
    assert clinvar_evidence(path, cfg, conflicting_ok=False) is True

    conf = {
        "clinical_significance": "Conflicting interpretations of pathogenicity",
        "gold_stars": 1,
    }
    # conflicting OFF by default -> no evidence
    assert clinvar_evidence(conf, cfg, conflicting_ok=True) is False
    # conflicting ON + resolved
    cfg_on = FilterConfig(include_conflicting=True)
    assert clinvar_evidence(conf, cfg_on, conflicting_ok=True) is True
    assert clinvar_evidence(conf, cfg_on, conflicting_ok=False) is False


def test_qualifies_lof_hc_alone() -> None:
    cfg = FilterConfig()
    assert qualifies(_csq(lof="HC"), has_clinvar_evidence=False, config=cfg) is True
    # lof disabled
    assert (
        qualifies(
            _csq(lof="HC"), has_clinvar_evidence=False, config=FilterConfig(lof_hc_enabled=False)
        )
        is False
    )


def test_qualifies_missense_requires_clinvar() -> None:
    cfg = FilterConfig()
    csq = _csq(consequence_terms=["missense_variant"])
    assert qualifies(csq, has_clinvar_evidence=False, config=cfg) is False
    assert qualifies(csq, has_clinvar_evidence=True, config=cfg) is True
    # missense disabled -> never qualifies on missense
    assert (
        qualifies(csq, has_clinvar_evidence=True, config=FilterConfig(missense_enabled=False))
        is False
    )


def test_qualifies_other_consequence_with_clinvar() -> None:
    cfg = FilterConfig()
    csq = _csq(consequence_terms=["splice_acceptor_variant"])
    assert qualifies(csq, has_clinvar_evidence=True, config=cfg) is True
    assert qualifies(csq, has_clinvar_evidence=False, config=cfg) is False


def test_qualifies_none_consequence_with_clinvar() -> None:
    cfg = FilterConfig()
    assert qualifies(None, has_clinvar_evidence=True, config=cfg) is True
    assert qualifies(None, has_clinvar_evidence=False, config=cfg) is False


# --- conflicting threshold ---


def test_meets_conflicting_threshold() -> None:
    subs = [
        {"clinical_significance": "Pathogenic"},
        {"clinical_significance": "Likely pathogenic"},
        {"clinical_significance": "Uncertain significance"},
        {"clinical_significance": "not provided"},  # skipped (not valid)
    ]
    # valid = 3 (P, LP, VUS); pathogenic = 2 -> 66.7%
    assert meets_conflicting_threshold(subs, 80.0) is False
    assert meets_conflicting_threshold(subs, 60.0) is True


def test_meets_conflicting_threshold_empty() -> None:
    assert meets_conflicting_threshold([], 80.0) is False


# --- quality flags ---


def test_is_high_af_ba1() -> None:
    assert is_high_af(0.06, 0.05) is True
    assert is_high_af(0.04, 0.05) is False


def test_is_gnomad_filtered() -> None:
    assert is_gnomad_filtered({"filters": ["AC0"]}, None) is True
    assert is_gnomad_filtered({"filters": []}, {"filters": ["PASS"]}) is False
    assert is_gnomad_filtered({"filters": ["PASS"]}, None) is False


def test_is_genomes_only() -> None:
    assert is_genomes_only(None, {"ac": 5, "an": 1000}) is True
    assert is_genomes_only({"ac": 1, "an": 1000}, {"ac": 5, "an": 1000}) is False


def test_is_high_hom_relative_and_absolute() -> None:
    # af=0.01, individuals=5000 -> expected hom = 0.5; observed 10 > 5*0.5=2.5 -> relative flag
    assert is_high_hom(observed_hom=10, af=0.01, individuals=5000, method="hwe_relative") is True
    assert is_high_hom(observed_hom=2, af=0.01, individuals=5000, method="hwe_relative") is False
    assert (
        is_high_hom(
            observed_hom=10, af=0.0, individuals=5000, method="absolute", absolute_threshold=10
        )
        is True
    )
    assert (
        is_high_hom(
            observed_hom=9, af=0.0, individuals=5000, method="absolute", absolute_threshold=10
        )
        is False
    )
