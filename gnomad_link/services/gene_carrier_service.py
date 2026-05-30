"""Gene-level carrier-frequency orchestration service.

Ports the gnomad-carrier-frequency pipeline: fetch a gene's variants (enriched
with per-population counts, LOFTEE, and ClinVar), keep the qualifying pathogenic
variants, then aggregate per-population and global carrier frequency. Pure math
lives in gene_carrier_math; predicates in gene_carrier_filters.
"""

from __future__ import annotations

from typing import Any, Protocol

from gnomad_link.services.gene_carrier_filters import (
    FilterConfig,
    clinvar_evidence,
    is_conflicting,
    is_genomes_only,
    is_gnomad_filtered,
    is_hc_lof,
    is_high_af,
    is_high_hom,
    meets_conflicting_threshold,
    qualifies,
)
from gnomad_link.services.gene_carrier_math import aggregate_carrier

# gnomAD population codes reported per version (continental; no sex-split/subcontinental).
_POPULATIONS: dict[str, list[str]] = {
    "gnomad_r4": ["afr", "amr", "asj", "eas", "fin", "mid", "nfe", "sas"],
    "gnomad_r3": ["afr", "ami", "amr", "asj", "eas", "fin", "nfe", "sas"],
    "gnomad_r2_1": ["afr", "amr", "asj", "eas", "fin", "nfe", "oth", "sas"],
}
_HIGH_AF_THRESHOLD = 0.05


class _GeneCarrierClient(Protocol):
    async def get_gene_carrier_variants(
        self,
        *,
        gene_id: str | None = None,
        gene_symbol: str | None = None,
        dataset: str = "gnomad_r4",
    ) -> dict[str, Any]: ...

    async def get_clinvar_variant(
        self,
        variant_id: str,
        reference_genome: str | None = None,
        dataset: str | None = None,
    ) -> dict[str, Any]: ...


def _reference_genome(dataset: str) -> str:
    return "GRCh37" if dataset == "gnomad_r2_1" else "GRCh38"


def _resolve_counts(variant: dict[str, Any], pop_id: str | None) -> tuple[int, int, int]:
    """Per-population (or global when pop_id is None) (ac, an, hom), joint-first."""
    joint = variant.get("joint")
    if joint:
        if pop_id is None:
            return (joint.get("ac") or 0, joint.get("an") or 0, joint.get("homozygote_count") or 0)
        for pop in joint.get("populations") or []:
            if pop.get("id") == pop_id:
                return (pop.get("ac") or 0, pop.get("an") or 0, pop.get("homozygote_count") or 0)
        return (0, 0, 0)

    exome = variant.get("exome") or {}
    genome = variant.get("genome") or {}
    if pop_id is None:
        return (
            (exome.get("ac") or 0) + (genome.get("ac") or 0),
            (exome.get("an") or 0) + (genome.get("an") or 0),
            (exome.get("homozygote_count") or 0) + (genome.get("homozygote_count") or 0),
        )
    exome_pop = _find_pop(exome, pop_id)
    genome_pop = _find_pop(genome, pop_id)
    return (
        (exome_pop.get("ac") or 0) + (genome_pop.get("ac") or 0),
        (exome_pop.get("an") or 0) + (genome_pop.get("an") or 0),
        (exome_pop.get("homozygote_count") or 0) + (genome_pop.get("homozygote_count") or 0),
    )


def _find_pop(source: dict[str, Any], pop_id: str) -> dict[str, Any]:
    populations: list[dict[str, Any]] = source.get("populations") or []
    for pop in populations:
        if pop.get("id") == pop_id:
            return pop
    return {}


class GeneCarrierService:
    """Assemble gene-level carrier frequency from the unified gnomAD client."""

    def __init__(self, client: _GeneCarrierClient) -> None:
        self.client = client

    async def get_gene_carrier_frequency(
        self,
        *,
        gene_id: str | None = None,
        gene_symbol: str | None = None,
        dataset: str = "gnomad_r4",
        filter_config: FilterConfig | None = None,
        method: str = "hom_exclusion",
        penetrance: float = 1.0,
        exclude_high_af: bool = False,
        exclude_high_hom: bool = False,
        exclude_gnomad_filtered: bool = False,
        exclude_genomes_only: bool = False,
        high_hom_method: str = "hwe_relative",
    ) -> dict[str, Any]:
        config = filter_config or FilterConfig()
        raw = await self.client.get_gene_carrier_variants(
            gene_id=gene_id, gene_symbol=gene_symbol, dataset=dataset
        )
        gene = raw.get("gene")
        if not gene or not gene.get("variants"):
            from gnomad_link.api.base_client import DataNotFoundError

            raise DataNotFoundError(f"No variants for gene {gene_id or gene_symbol} in {dataset}")

        clinvar_map: dict[str, Any] = {
            str(cv.get("variant_id")): cv for cv in (gene.get("clinvar_variants") or [])
        }
        conflicting_ok = await self._resolve_conflicting(
            gene["variants"], clinvar_map, config, dataset
        )

        qualifying = self._select_qualifying(
            gene["variants"],
            clinvar_map,
            config,
            conflicting_ok,
            exclude_high_af=exclude_high_af,
            exclude_high_hom=exclude_high_hom,
            exclude_gnomad_filtered=exclude_gnomad_filtered,
            exclude_genomes_only=exclude_genomes_only,
            high_hom_method=high_hom_method,
        )

        populations = {
            pop_id: aggregate_carrier(
                [_resolve_counts(v["variant"], pop_id) for v in qualifying],
                method=method,
                penetrance=penetrance,
            )
            for pop_id in _POPULATIONS.get(dataset, _POPULATIONS["gnomad_r4"])
        }
        global_metrics = aggregate_carrier(
            [_resolve_counts(v["variant"], None) for v in qualifying],
            method=method,
            penetrance=penetrance,
        )

        sources = {"plof_only": 0, "clinvar_only": 0, "both": 0}
        for item in qualifying:
            sources[item["source"]] += 1

        return {
            "gene": {"gene_id": gene.get("gene_id"), "symbol": gene.get("symbol")},
            "dataset": dataset,
            "reference_genome": _reference_genome(dataset),
            "settings": {
                "method": method,
                "penetrance": penetrance,
                "include_lof_hc": config.lof_hc_enabled,
                "include_missense": config.missense_enabled,
                "include_clinvar": config.clinvar_enabled,
                "clinvar_star_threshold": config.clinvar_star_threshold,
                "include_conflicting_clinvar": config.include_conflicting,
            },
            "global": global_metrics,
            "populations": populations,
            "qualifying_variants": [item["summary"] for item in qualifying],
            "qualifying_count": len(qualifying),
            "sources": sources,
        }

    async def _resolve_conflicting(
        self,
        variants: list[dict[str, Any]],
        clinvar_map: dict[str, Any],
        config: FilterConfig,
        dataset: str,
    ) -> dict[str, bool]:
        """For opt-in conflicting ClinVar, fetch submissions and resolve P/LP share."""
        if not (config.clinvar_enabled and config.include_conflicting):
            return {}
        reference_genome = _reference_genome(dataset)
        resolved: dict[str, bool] = {}
        for variant in variants:
            vid = str(variant.get("variant_id") or "")
            clinvar = clinvar_map.get(vid)
            if not clinvar or not is_conflicting(clinvar):
                continue
            # LoF HC variants qualify without ClinVar; skip the extra fetch for them.
            if config.lof_hc_enabled and is_hc_lof(variant.get("transcript_consequence")):
                continue
            try:
                payload = await self.client.get_clinvar_variant(vid, reference_genome)
            except Exception:
                resolved[vid] = False
                continue
            submissions = (payload.get("clinvar_variant") or {}).get("submissions") or []
            resolved[vid] = meets_conflicting_threshold(submissions, config.conflicting_threshold)
        return resolved

    def _select_qualifying(
        self,
        variants: list[dict[str, Any]],
        clinvar_map: dict[str, Any],
        config: FilterConfig,
        conflicting_ok: dict[str, bool],
        *,
        exclude_high_af: bool,
        exclude_high_hom: bool,
        exclude_gnomad_filtered: bool,
        exclude_genomes_only: bool,
        high_hom_method: str,
    ) -> list[dict[str, Any]]:
        qualifying: list[dict[str, Any]] = []
        for variant in variants:
            vid = str(variant.get("variant_id") or "")
            ac, an, hom = _resolve_counts(variant, None)
            if ac <= 0:  # AC>0 guard
                continue
            consequence = variant.get("transcript_consequence")
            clinvar = clinvar_map.get(vid)
            has_clinvar = clinvar_evidence(
                clinvar, config, conflicting_ok=conflicting_ok.get(vid, False)
            )
            if not qualifies(consequence, has_clinvar_evidence=has_clinvar, config=config):
                continue

            af = ac / an if an > 0 else 0.0
            flags = self._quality_flags(variant, af, ac, an, hom, high_hom_method)
            if (
                (exclude_high_af and "high_af" in flags)
                or (exclude_high_hom and "high_hom" in flags)
                or (exclude_gnomad_filtered and "gnomad_filtered" in flags)
                or (exclude_genomes_only and "genomes_only" in flags)
            ):
                continue

            lof_hc = config.lof_hc_enabled and is_hc_lof(consequence)
            source = (
                "both" if lof_hc and has_clinvar else ("plof_only" if lof_hc else "clinvar_only")
            )
            qualifying.append(
                {
                    "variant": variant,
                    "source": source,
                    "summary": {
                        "variant_id": vid,
                        "major_consequence": (consequence or {}).get("major_consequence"),
                        "global_af": af,
                        "global_ac": ac,
                        "clinvar_significance": (clinvar or {}).get("clinical_significance"),
                        "gold_stars": (clinvar or {}).get("gold_stars"),
                        "source": source,
                        "flags": flags,
                    },
                }
            )
        return qualifying

    @staticmethod
    def _quality_flags(
        variant: dict[str, Any],
        af: float,
        ac: int,
        an: int,
        hom: int,
        high_hom_method: str,
    ) -> list[str]:
        flags: list[str] = []
        if is_high_af(af, _HIGH_AF_THRESHOLD):
            flags.append("high_af")
        if is_high_hom(
            observed_hom=hom, af=af, individuals=an / 2 if an else 0.0, method=high_hom_method
        ):
            flags.append("high_hom")
        if is_gnomad_filtered(variant.get("exome"), variant.get("genome")):
            flags.append("gnomad_filtered")
        if is_genomes_only(variant.get("exome"), variant.get("genome")):
            flags.append("genomes_only")
        return flags
