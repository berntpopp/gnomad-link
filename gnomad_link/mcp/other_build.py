"""On a variant not_found, look the id up once in the other genome build (#145)."""

from __future__ import annotations

from async_lru import alru_cache

from gnomad_link.api import DataNotFoundError
from gnomad_link.config import settings
from gnomad_link.mcp.build_check import dataset_build, detect_variant_id_mismatch
from gnomad_link.mcp.errors import McpErrorContext, McpToolError, mcp_tool_error
from gnomad_link.services import FrequencyService


@alru_cache(maxsize=settings.CACHE_SIZE, ttl=settings.CACHE_TTL_MINUTES * 60)
async def _variant_exists(service: FrequencyService, vid: str, dataset: str) -> bool:
    """Whether the id is in the dataset. Absence is cached too; errors never are."""
    try:
        await service.get_variant_frequencies(vid, dataset)
    except DataNotFoundError:
        return False
    return True


async def not_found_with_other_build(
    service: FrequencyService, exc: DataNotFoundError, ctx: McpErrorContext
) -> McpToolError:
    """Return the not_found envelope, naming what the other build's dataset holds.

    Costs at most ONE extra upstream request (cached, and paced by the client's
    rate limiter). A hit does not prove the caller meant that build -- the same
    CHROM-POS-REF-ALT can exist in both as different variants -- so the envelope
    names the dataset (``found_in``) and never makes the re-call the first step.
    """
    error = mcp_tool_error(exc, ctx)
    vid, dataset = ctx.variant_id or "", ctx.dataset or "gnomad_r4"
    other = "gnomad_r4" if dataset == "gnomad_r2_1" else "gnomad_r2_1"
    build, other_build = dataset_build(dataset), dataset_build(other)
    if detect_variant_id_mismatch(vid, other) is not None:
        return error  # the position lies beyond the other build's chromosome end
    payload = error.payload
    try:
        exists = await _variant_exists(service, vid, other)
    except Exception:
        return error  # the probe is best-effort: keep the plain not_found
    if not exists:
        payload["message"] = (
            f"Variant {vid} is absent from gnomAD under this id in both builds "
            f"({dataset}, {build}; {other}, {other_build})."
        )
        payload["recovery"] = (
            "Not a retry, and switching dataset will not help: this id is in neither "
            "build's dataset. Treat it as not observed in gnomAD unless the coordinate "
            "is known to be from the other build, in which case lift it over once."
        )
        return error
    recall = {"tool": ctx.tool_name, "arguments": {"variant_id": vid, "dataset": other}}
    payload["message"] = (
        f"Variant {vid} is not in {dataset} ({build}). The same id exists in {other} "
        f"({other_build}); use it only if your coordinates are on {other_build}."
    )
    payload["recovery"] = (
        f"Check which build your coordinates are on. If {other_build}: call {ctx.tool_name} "
        f"with dataset='{other}'. If {build}: the variant is not in {dataset}; the "
        f"{other} record under this id is a different variant."
    )
    payload["found_in"] = {"dataset": other, "reference_genome": other_build}
    # The same CHROM-POS-REF-ALT can be a different variant in the other build, so the
    # re-call is never the fallback or the first step: it follows the liftover check.
    commands = payload["_meta"]["next_commands"]
    after = next(
        (i + 1 for i, c in enumerate(commands) if c["tool"] == "compute_variant_liftover"), None
    )
    if after is not None:
        commands.insert(after, recall)
    return error
