"""Gene tools: get_gene_details, get_gene_variants."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.errors import McpErrorContext, ToolInputError, run_mcp_tool
from gnomad_link.mcp.foreign_ids import reject_foreign
from gnomad_link.mcp.headline import gene_details_headline
from gnomad_link.mcp.minimal_shaping import project_gene_details_minimal
from gnomad_link.mcp.next_commands import cmd
from gnomad_link.mcp.patterns import GENE_ID_PATTERN, GENE_SYMBOL_PATTERN, split_gene
from gnomad_link.mcp.shaping import shape_gene_details_compact, shape_gene_variants
from gnomad_link.services import FrequencyService

# gnomAD VEP major_consequence vocabulary (a superset is safe: the runtime accepts
# any declared value; an out-of-vocab value is rejected as invalid_input by the
# schema instead of silently returning zero rows). Declared as a Literal so the
# behaviour gate's declared-enum probe covers this filter.
GeneVariantConsequence = Literal[
    "transcript_ablation",
    "splice_acceptor_variant",
    "splice_donor_variant",
    "stop_gained",
    "frameshift_variant",
    "stop_lost",
    "start_lost",
    "transcript_amplification",
    "inframe_insertion",
    "inframe_deletion",
    "missense_variant",
    "protein_altering_variant",
    "splice_region_variant",
    "incomplete_terminal_codon_variant",
    "start_retained_variant",
    "stop_retained_variant",
    "synonymous_variant",
    "coding_sequence_variant",
    "mature_miRNA_variant",
    "5_prime_UTR_variant",
    "3_prime_UTR_variant",
    "non_coding_transcript_exon_variant",
    "intron_variant",
    "NMD_transcript_variant",
    "non_coding_transcript_variant",
    "upstream_gene_variant",
    "downstream_gene_variant",
    "TFBS_ablation",
    "TFBS_amplification",
    "TF_binding_site_variant",
    "regulatory_region_ablation",
    "regulatory_region_amplification",
    "feature_elongation",
    "regulatory_region_variant",
    "feature_truncation",
    "intergenic_variant",
]


def register_gene_tools(mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]) -> None:
    @mcp.tool(
        name="get_gene_details",
        title="Get Gene Details",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=None,
        tags={"gene"},
    )
    async def get_gene_details(
        gene: Annotated[
            str,
            Field(
                description="Gene symbol (e.g. PCSK9) or Ensembl gene ID (ENSG...).",
                examples=["PCSK9"],
            ),
        ],
        reference_genome: Annotated[
            Literal["GRCh37", "GRCh38"],
            Field(description="Lookup build for gene coordinates and constraint. GRCh38 default."),
        ] = "GRCh38",
        response_mode: Annotated[
            Literal["compact", "full", "minimal"],
            Field(
                description=(
                    "compact drops heavy arrays (transcripts, exons, alt_transcripts) and "
                    "emits a truncated block; full passes through everything; minimal returns the "
                    "headline + symbol/gene_id + pLI/oe_lof + coordinates + _meta only."
                )
            ),
        ] = "compact",
    ) -> dict[str, Any]:
        """Use this when a caller has a gene id or symbol; returns constraint scores (pLI/oe_lof), canonical transcript, and basic coordinates (chrom/start/stop only: gnomAD has no cytogenetic band; that is HGNC `location`, via hgnc_resolve_symbol). Follow with get_gene_variants if they then need per-variant rows. Returns compact ~2kB, full up to ~30kB."""

        gene_id, gene_symbol = split_gene(gene)

        async def call() -> dict[str, Any]:
            reject_foreign(gene, "gene", field="gene", tool="get_gene_details")
            service = service_factory()
            gene_obj = await service.get_gene(
                gene_id=gene_id,
                gene_symbol=gene_symbol,
                reference_genome=reference_genome,
            )
            result: dict[str, Any] = (
                gene_obj.model_dump() if hasattr(gene_obj, "model_dump") else dict(gene_obj)
            )
            if response_mode in ("compact", "minimal"):
                result = shape_gene_details_compact(result)
            # Lead with the plain-English headline so an LLM can answer fast.
            result = {
                "headline": gene_details_headline(result, reference_genome=reference_genome),
                **result,
            }
            # Suggest the natural follow-up call using the resolved gene_id.
            resolved_id = result.get("gene_id") or gene_id
            if resolved_id:
                existing_meta: dict[str, Any] = result.get("_meta") or {}
                existing_next: list[Any] = existing_meta.get("next_commands", [])
                variants_cmd: dict[str, Any] = {
                    "tool": "get_gene_variants",
                    "arguments": {"gene_id": resolved_id},
                }
                next_cmds = [*existing_next, variants_cmd]
                if result.get("symbol"):
                    # gnomAD has no cytogenetic band; HGNC `location` does (cross-server, #138).
                    next_cmds.append(cmd("hgnc_resolve_symbol", query=result["symbol"]))
                result["_meta"] = {**existing_meta, "next_commands": next_cmds}
            if response_mode == "minimal":
                return project_gene_details_minimal(result)
            return result

        return await run_mcp_tool(
            "get_gene_details",
            call,
            context=McpErrorContext(
                tool_name="get_gene_details",
                gene_id=gene_id,
                gene_symbol=gene_symbol,
            ),
        )

    @mcp.tool(
        name="get_gene_variants",
        title="Get Gene Variants",
        annotations=READ_ONLY_OPEN_WORLD,
        tags={"gene"},
        output_schema=None,
    )
    async def get_gene_variants(
        gene_id: Annotated[
            str,
            Field(
                description="Ensembl gene ID or gene symbol.",
                examples=["ENSG00000169174"],
            ),
        ],
        dataset: Annotated[
            Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"],
            Field(
                description="gnomad_r4 (GRCh38, default, largest cohort), gnomad_r3 (GRCh38, whole-genome), gnomad_r2_1 (GRCh37 legacy)",
                examples=["gnomad_r4"],
            ),
        ] = "gnomad_r4",
        limit: Annotated[
            int, Field(ge=1, le=500, description="Max variants returned (hard cap 500).")
        ] = 100,
        consequence: Annotated[
            GeneVariantConsequence | None,
            Field(
                description="Exact VEP major_consequence term to keep (e.g. "
                "'missense_variant', 'stop_gained'); not a category like 'lof'. "
                "An unrecognised term is rejected as invalid_input, not zeroed."
            ),
        ] = None,
        max_af: Annotated[
            float | None,
            Field(ge=0.0, le=1.0, description="Drop variants whose AF exceeds this threshold."),
        ] = None,
        min_ac: Annotated[
            int | None, Field(ge=0, description="Drop variants whose AC is below this threshold.")
        ] = None,
        include_populations: Annotated[
            bool,
            Field(
                description=(
                    "Keep each variant's per-population breakdown (trimmed). Set False to "
                    "drop the population arrays entirely (keeps ac/an/af) for a lean list scan "
                    "— the biggest token saving."
                )
            ),
        ] = True,
        include_subcohorts: Annotated[
            bool,
            Field(description="Include non_topmed_*, non_ukb_*, 1kg_*, hgdp_*, controls_* rows."),
        ] = False,
        include_sex_split: Annotated[
            bool,
            Field(description="Include _XX/_XY sex-split rows."),
        ] = False,
        exclude_zero_populations: Annotated[
            bool,
            Field(description="Drop populations with allele_count == 0 from each variant."),
        ] = True,
    ) -> dict[str, Any]:
        """Use this when a caller wants per-variant rows for a gene (ENSG/symbol); returns each variant's id, consequence, HGVS, and AC/AN/AF. Caps large results at 500; consequence/AF/AC filters and include_populations control payload size. Reports cap use in `truncated` and describes retained population fields in `population_projection`. Returns ~5-45kB at the default limit=100."""

        ensg, symbol = split_gene(gene_id)

        async def call() -> dict[str, Any]:
            reject_foreign(gene_id, "gene", field="gene_id", tool="get_gene_variants")
            if not re.fullmatch(
                GENE_ID_PATTERN if ensg else GENE_SYMBOL_PATTERN, gene_id, re.ASCII
            ):
                raise ToolInputError(
                    "gene_id must be an Ensembl gene id (ENSG + 11 digits) or a gene symbol."
                )
            service = service_factory()
            resolved_from: dict[str, str] | None = None
            if symbol:
                # Same single upstream request as the id path: gnomAD looks the gene up by symbol.
                gene = await service.get_gene_with_variants(symbol, dataset)
                raw = list(gene.get("variants") or [])
                if gene.get("gene_id"):
                    resolved_from = {
                        "input": symbol,
                        "form": "symbol",
                        "resolved_to": gene["gene_id"],
                    }
            else:
                raw = await service.get_gene_variants(gene_id, dataset)
            gene_ref = resolved_from["resolved_to"] if resolved_from else gene_id
            result = shape_gene_variants(
                raw,
                limit=limit,
                consequence=consequence,
                max_af=max_af,
                min_ac=min_ac,
                include_populations=include_populations,
                include_subcohorts=include_subcohorts,
                include_sex_split=include_sex_split,
                exclude_zero_populations=exclude_zero_populations,
            )
            # Follow up with gene-level context, and ClinVar for the first row.
            variants = result.get("variants") or []
            cmds = [cmd("get_gene_details", gene=gene_ref)]
            if variants and variants[0].get("variant_id"):
                cmds.append(
                    cmd("get_clinvar_variant_details", variant_id=variants[0]["variant_id"])
                )
            result.setdefault("_meta", {})["next_commands"] = cmds
            if resolved_from:
                result["resolved_from"] = resolved_from
            return result

        return await run_mcp_tool(
            "get_gene_variants",
            call,
            context=McpErrorContext(
                tool_name="get_gene_variants",
                gene_id=ensg,
                gene_symbol=symbol,
                dataset=dataset,
            ),
        )
