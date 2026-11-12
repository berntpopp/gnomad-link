"""Search and identifier-resolution tools."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.af import preferred_overall_af
from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.errors import McpErrorContext, ToolInputError, run_mcp_tool
from gnomad_link.mcp.next_commands import for_variant
from gnomad_link.mcp.patterns import MITO_VARIANT_ID_PATTERN, normalize_mito_variant_id
from gnomad_link.models import GeneSearchResult
from gnomad_link.services import FrequencyService
from gnomad_link.services.frequency_service import _pick_canonical_annotation

_RANK_ORDER = {
    "exact_symbol": 0,
    "exact_ensembl_id": 1,
    "prefix": 2,
    "substring": 3,
}

# Cap second-pass enrichment cost: only fetch frequencies for the first N hits.
_ENRICHMENT_CAP = 5

_MITO_ID_RE = re.compile(MITO_VARIANT_ID_PATTERN)
_MITO_NEXT_STEPS = [
    "Call get_mitochondrial_variant(variant_id, dataset) for homoplasmic/heteroplasmic "
    "frequencies; get_variant_frequencies does not serve chrM.",
]


def _resolver_context(tool_name: str, query: str) -> McpErrorContext:
    """Error context; a chrM query carries its normalized id so errors route to mito."""
    q = query.strip()
    mito_id = normalize_mito_variant_id(q).upper() if _MITO_ID_RE.fullmatch(q) else None
    return McpErrorContext(tool_name=tool_name, query=query, variant_id=mito_id)


def _is_mito(results: list[dict[str, Any]]) -> bool:
    return bool(results) and results[0].get("variant_type") == "mitochondrial"


async def _enrich_variant_id(
    service: FrequencyService, variant_id: str, dataset: str
) -> dict[str, Any]:
    """Second-pass fetch to attach gene/consequence/af to a search hit.

    Returns the enrichment fields on success, or an empty dict if the upstream
    call fails. Enrichment is best-effort and must not block the response.
    """
    try:
        freq = await service.get_variant_frequencies(variant_id, dataset)
    except Exception:
        return {}
    af, af_source = preferred_overall_af(freq.exome, freq.genome)
    return {
        "gene_symbol": freq.gene_symbol,
        "major_consequence": freq.major_consequence,
        "af": af,
        "af_source": af_source,
    }


async def _resolve_and_enrich(
    service: FrequencyService,
    *,
    query: str,
    dataset: str,
    limit: int,
    enrich: bool,
) -> tuple[list[dict[str, Any]], int, int]:
    """Resolve `query` to variant IDs and optionally enrich the top hits.

    Returns the result list, the count of enrichment failures (so the caller can
    attach ``_meta.enrichment_partial``), and the TOTAL number of candidates the
    upstream returned before the ``limit`` slice -- so the caller can report an
    honest ``total_count`` / ``has_more`` instead of making 5 candidates at
    ``limit=1`` look like 1.
    """
    if _MITO_ID_RE.fullmatch(query.strip()):
        return await _resolve_mito(service, query=query.strip(), dataset=dataset, enrich=enrich)
    raw = await service.search_variants(query, dataset)
    total_available = len(raw)
    ids = raw[:limit]
    enrichment_failures = 0
    results: list[dict[str, Any]] = []
    for idx, vid in enumerate(ids):
        item: dict[str, Any] = {"variant_id": vid}
        if enrich and idx < _ENRICHMENT_CAP:
            enriched = await _enrich_variant_id(service, vid, dataset)
            if enriched:
                item.update(enriched)
            else:
                enrichment_failures += 1
        results.append(item)
    return results, enrichment_failures, total_available


async def _resolve_mito(
    service: FrequencyService, *, query: str, dataset: str, enrich: bool
) -> tuple[list[dict[str, Any]], int, int]:
    """Resolve a chrM id via the dedicated mitochondrial endpoint (#127).

    gnomAD's variant_search does not index mitochondrial variants, so passing an
    M-/MT- id through it yields an empty success that reads as "absent". An absent
    mito id raises not_found from the mitochondrial lookup instead.
    """
    if dataset == "gnomad_r2_1":
        raise ToolInputError(
            "gnomad_r2_1 has no mitochondrial variants; use dataset gnomad_r4 or "
            "gnomad_r3, or call get_mitochondrial_variant."
        )
    vid = normalize_mito_variant_id(query).upper()
    raw = await service.get_mitochondrial_variant(vid, dataset)
    mv = raw.get("mitochondrial_variant", raw) or {}
    item: dict[str, Any] = {
        "variant_id": mv.get("variant_id") or vid,
        "variant_type": "mitochondrial",
    }
    an = mv.get("an")
    if enrich:
        gene_symbol, consequence = _pick_canonical_annotation(mv.get("transcript_consequences"))
        item.update(gene_symbol=gene_symbol, major_consequence=consequence)
        if an:
            item["af_hom"] = (mv.get("ac_hom") or 0) / an
            item["af_het"] = (mv.get("ac_het") or 0) / an
        # A failing site reads as AF 0.0; surface why (e.g. "No passing genotype").
        item["filters"] = mv.get("filters") or []
    return [item], 0, 1


def _classify_gene_match(hit: GeneSearchResult, query_upper: str) -> str:
    """Classify how `query_upper` matches the given gene search hit.

    Order of preference: exact symbol, exact Ensembl id, prefix on either,
    falling back to substring.
    """
    sym = (hit.symbol or "").upper()
    gid = (hit.ensembl_id or "").upper()
    if sym == query_upper:
        return "exact_symbol"
    if gid == query_upper:
        return "exact_ensembl_id"
    if sym.startswith(query_upper) or gid.startswith(query_upper):
        return "prefix"
    return "substring"


def register_search_tools(mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]) -> None:
    @mcp.tool(
        name="search_genes",
        title="Search Genes",
        annotations=READ_ONLY_OPEN_WORLD,
        tags={"gene", "search"},
        output_schema=None,
    )
    async def search_genes(
        query: Annotated[
            str,
            Field(
                min_length=2,
                max_length=100,
                description="Gene symbol, name fragment, or Ensembl ID.",
                examples=["BRCA1"],
            ),
        ],
        reference_genome: Annotated[
            Literal["GRCh37", "GRCh38"],
            Field(description="Reference build to search gene symbols/ids within. GRCh38 default."),
        ] = "GRCh38",
        limit: Annotated[
            int,
            Field(ge=1, le=50, description="Max matches returned."),
        ] = 25,
    ) -> dict[str, Any]:
        """Use this when a caller has a fuzzy gene query (symbol, alias, partial name). Follow with get_gene_details for full constraint metrics. Note: gnomAD's gene autocomplete returns a bounded set and may omit exact members of a large gene family for a SHORT prefix (e.g. 'GRIN' does not return GRIN1/GRIN2B). If an expected gene is missing, query its FULL symbol (e.g. 'GRIN1') or call get_gene_details/get_gene_summary directly. Returns ~1-3kB."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            raw = await service.search_genes(query, reference_genome)
            query_upper = query.upper()
            ranked: list[tuple[int, int, GeneSearchResult]] = []
            for idx, hit in enumerate(raw):
                hit_model = (
                    hit
                    if isinstance(hit, GeneSearchResult)
                    else GeneSearchResult.model_validate(hit)
                )
                quality = _classify_gene_match(hit_model, query_upper)
                hit_with_quality = hit_model.model_copy(update={"match_quality": quality})
                ranked.append((_RANK_ORDER[quality], idx, hit_with_quality))
            ranked.sort(key=lambda t: (t[0], t[1]))
            sorted_hits = [hit for _, _, hit in ranked]
            total = len(sorted_hits)
            items = sorted_hits[:limit]
            results = [r.model_dump() for r in items]
            payload: dict[str, Any] = {
                "results": results,
                "returned": len(results),
                # Honest pagination: total_count is the full match count (invariant
                # under limit), has_more says the page did not exhaust it.
                "total_count": total,
                "has_more": total > len(results),
            }
            if total > len(results):
                payload["truncated"] = {
                    "kind": "search_results",
                    "total_seen": total,
                    "to_disable": "raise limit (max 50) or refine the query",
                }
            # gnomAD's autocomplete is upstream-bounded and can omit exact family
            # members for a short prefix with no exact hit (e.g. 'GRIN' drops
            # GRIN1/GRIN2B). Surface an actionable recovery instead of silently
            # returning an incomplete list.
            has_exact = any(r.get("match_quality") == "exact_symbol" for r in results)
            if not has_exact and len(query) <= 5:
                payload["search_hint"] = (
                    "gnomAD autocomplete may omit exact members of a gene family for a "
                    "short query. If an expected gene is missing, query its full symbol "
                    "(e.g. 'GRIN1') or call get_gene_details/get_gene_summary directly."
                )
            # Close the gene workflow's first hop: chain the top hit straight into
            # get_gene_details so the LLM does not have to re-form the call.
            if results:
                top = results[0]
                gene_value = top.get("ensembl_id") or top.get("symbol")
                if gene_value:
                    payload["_meta"] = {
                        "next_commands": [
                            {"tool": "get_gene_details", "arguments": {"gene": gene_value}}
                        ]
                    }
            return payload

        return await run_mcp_tool(
            "search_genes",
            call,
            context=McpErrorContext(tool_name="search_genes"),
        )

    @mcp.tool(
        name="resolve_variant_id",
        title="Resolve Variant Identifier",
        annotations=READ_ONLY_OPEN_WORLD,
        tags={"search"},
        output_schema=None,
    )
    async def resolve_variant_id(
        query: Annotated[
            str,
            Field(
                min_length=3,
                max_length=100,
                description="rsID, CHROM-POS-REF-ALT, 'CHROM:POS', or a chrM id (M-POS-REF-ALT).",
                examples=["rs80357906"],
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
            int, Field(ge=1, le=25, description="Max candidate variant ids returned.")
        ] = 10,
        enrich: Annotated[
            bool,
            Field(
                description=(
                    "Second-pass fetch gene_symbol, major_consequence, and AF "
                    f"for the top {_ENRICHMENT_CAP} hits."
                ),
            ),
        ] = True,
    ) -> dict[str, Any]:
        """Use this when the caller only has an rsID, partial coordinates, or text fragment and needs to obtain a canonical gnomAD variant id. With enrich=True (default) the top hits include gene_symbol, major_consequence, and AF so the caller can rank candidates without a follow-up call. Mitochondrial ids (M-/MT-/chrM-POS-REF-ALT) resolve via the gnomAD mitochondrial dataset (gnomad_r4/r3 only) with af_hom/af_het; follow up with get_mitochondrial_variant. Returns ~1-5kB (enrichment dependent)."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            results, enrichment_failures, total_available = await _resolve_and_enrich(
                service,
                query=query,
                dataset=dataset,
                limit=limit,
                enrich=enrich,
            )
            payload: dict[str, Any] = {
                "results": results,
                "returned": len(results),
                # total_count is the FULL candidate count (invariant under limit);
                # has_more says the page did not exhaust it, so 5 candidates at
                # limit=1 never look like 1 (honest pagination).
                "total_count": total_available,
                "has_more": total_available > len(results),
                "next_steps": _MITO_NEXT_STEPS
                if _is_mito(results)
                else [
                    "Pick one variant_id and call get_variant_frequencies(variant_id, dataset).",
                    "Or call get_variant_details(variant_id, dataset) for annotations.",
                ],
            }
            if total_available > len(results):
                payload["truncated"] = {
                    "kind": "search_results",
                    "total_seen": total_available,
                    "to_disable": "raise limit (max 25) or refine the query",
                }
            meta: dict[str, Any] = {}
            if results:
                meta["next_commands"] = for_variant(results[0]["variant_id"], dataset)
            if enrichment_failures > 0:
                meta["enrichment_partial"] = True
                meta["enrichment_failures"] = enrichment_failures
            if meta:
                payload["_meta"] = meta
            return payload

        return await run_mcp_tool(
            "resolve_variant_id",
            call,
            context=_resolver_context("resolve_variant_id", query),
        )

    @mcp.tool(
        name="search_variants",
        title="Search Variants (deprecated alias)",
        annotations=READ_ONLY_OPEN_WORLD,
        tags={"search"},
        output_schema=None,
    )
    async def search_variants(
        query: Annotated[
            str,
            Field(
                min_length=3,
                max_length=100,
                description="rsID, CHROM-POS-REF-ALT, 'CHROM:POS', or a chrM id (M-POS-REF-ALT).",
                examples=["rs80357906"],
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
            int, Field(ge=1, le=25, description="Max candidate variant ids returned.")
        ] = 10,
        enrich: Annotated[
            bool,
            Field(
                description=(
                    "Second-pass fetch gene_symbol, major_consequence, and AF "
                    f"for the top {_ENRICHMENT_CAP} hits."
                ),
            ),
        ] = True,
    ) -> dict[str, Any]:
        """Use this when a caller uses the legacy tool name -- deprecated alias for resolve_variant_id. Mirrors the same enrichment behaviour; will be removed in the next release. Returns ~1-5kB (deprecated alias)."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            results, enrichment_failures, total_available = await _resolve_and_enrich(
                service,
                query=query,
                dataset=dataset,
                limit=limit,
                enrich=enrich,
            )
            meta: dict[str, Any] = {
                "deprecated": True,
                "use_instead": "resolve_variant_id",
            }
            if enrichment_failures > 0:
                meta["enrichment_partial"] = True
                meta["enrichment_failures"] = enrichment_failures
            if results:
                meta["next_commands"] = for_variant(results[0]["variant_id"], dataset)
            payload: dict[str, Any] = {
                "results": results,
                "returned": len(results),
                "total_count": total_available,
                "has_more": total_available > len(results),
                "next_steps": _MITO_NEXT_STEPS
                if _is_mito(results)
                else [
                    "Pick one variant_id and call get_variant_frequencies(variant_id, dataset).",
                ],
                "_meta": meta,
            }
            if total_available > len(results):
                payload["truncated"] = {
                    "kind": "search_results",
                    "total_seen": total_available,
                    "to_disable": "raise limit (max 25) or refine the query",
                }
            return payload

        return await run_mcp_tool(
            "search_variants",
            call,
            context=_resolver_context("search_variants", query),
        )
