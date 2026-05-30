"""Service for searching gnomAD structural variants by gene or region.

Heavy orchestration (entry-arg dispatch, sv_dataset->build mapping, region
parsing) lives here so FrequencyService keeps only a thin delegating wrapper
and does not grow past its line budget. Client-side filtering and capping
live in gnomad_link/mcp/sv_shaping.py, not here.
"""

from __future__ import annotations

import re
from typing import Any

from gnomad_link.api.client import UnifiedGnomadClient

# StructuralVariantDatasetId -> reference build. gnomad_sv_r4 is GRCh38;
# gnomad_sv_r2_1 is GRCh37. This is a DISTINCT enum from the SNV DatasetId.
_SV_DATASET_BUILD: dict[str, str] = {
    "gnomad_sv_r4": "GRCh38",
    "gnomad_sv_r2_1": "GRCh37",
}

_REGION_RE = re.compile(r"^(?:chr)?([1-9]|1\d|2[0-2]|X|Y)-(\d+)-(\d+)$")


class StructuralVariantService:
    """Search structural variants overlapping a gene or region."""

    def __init__(self, client: UnifiedGnomadClient | None = None) -> None:
        self.client = client or UnifiedGnomadClient()

    async def search_structural_variants(
        self,
        *,
        gene_symbol: str | None = None,
        gene_id: str | None = None,
        region: str | None = None,
        sv_dataset: str = "gnomad_sv_r4",
    ) -> list[dict[str, Any]]:
        """Return the FULL list of SV rows for the entry argument.

        Exactly one of gene_symbol / gene_id / region must be provided.
        Filtering and capping are the caller's responsibility (sv_shaping).
        """
        provided = [v for v in (gene_symbol, gene_id, region) if v]
        if len(provided) != 1:
            raise ValueError("Provide exactly one of gene_symbol, gene_id, or region.")
        if sv_dataset not in _SV_DATASET_BUILD:
            raise ValueError("Invalid sv_dataset; expected gnomad_sv_r4 or gnomad_sv_r2_1.")
        reference_genome = _SV_DATASET_BUILD[sv_dataset]

        if region:
            match = _REGION_RE.match(region)
            if not match:
                raise ValueError(
                    "Invalid region; expected CHROM-START-STOP (e.g. 19-11089000-11200000)."
                )
            chrom, start_s, stop_s = match.groups()
            start, stop = int(start_s), int(stop_s)
            if stop <= start:
                raise ValueError("Region stop must be greater than start.")
            return await self.client.search_structural_variants_by_region(
                chrom=chrom,
                start=start,
                stop=stop,
                reference_genome=reference_genome,
                sv_dataset=sv_dataset,
            )

        return await self.client.search_structural_variants_by_gene(
            gene_id=gene_id,
            gene_symbol=gene_symbol,
            reference_genome=reference_genome,
            sv_dataset=sv_dataset,
        )
