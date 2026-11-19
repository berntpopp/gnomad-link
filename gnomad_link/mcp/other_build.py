"""On a variant not_found, look the id up once in the other genome build (#145)."""

from __future__ import annotations

from gnomad_link.api import DataNotFoundError
from gnomad_link.mcp.build_check import dataset_build, detect_variant_id_mismatch
from gnomad_link.mcp.errors import McpErrorContext, McpToolError, mcp_tool_error
from gnomad_link.services import FrequencyService


async def not_found_with_other_build(
    service: FrequencyService, exc: DataNotFoundError, ctx: McpErrorContext
) -> McpToolError:
    """Return the not_found envelope, naming what the other build's dataset holds.

    Costs at most ONE extra upstream request (cached, and paced by the client's
    rate limiter). A hit does not prove the caller meant that build -- the same
    CHROM-POS-REF-ALT can exist in both -- so the envelope names the dataset and
    the re-call instead of silently returning the other build's frequencies.
    """
    error = mcp_tool_error(exc, ctx)
    vid, dataset = ctx.variant_id or "", ctx.dataset or "gnomad_r4"
    other = "gnomad_r4" if dataset == "gnomad_r2_1" else "gnomad_r2_1"
    build, other_build = dataset_build(dataset), dataset_build(other)
    if detect_variant_id_mismatch(vid, other) is not None:
        return error  # the position lies beyond the other build's chromosome end
    payload = error.payload
    try:
        await service.get_variant_frequencies(vid, other)
    except DataNotFoundError:
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
    except Exception:
        return error  # the probe is best-effort: keep the plain not_found
    recall = {"variant_id": vid, "dataset": other}
    payload["message"] = (
        f"Variant {vid} is not in {dataset} ({build}), but the same id exists in "
        f"{other} ({other_build})."
    )
    payload["recovery"] = (
        f"The coordinates are probably {other_build}: call {ctx.tool_name} again with "
        f"dataset='{other}', or lift the id over to {build} to query {dataset}."
    )
    payload["recovery_action"] = "reformulate_input"
    payload["fallback_tool"], payload["fallback_args"] = ctx.tool_name, recall
    payload["found_in"] = {"dataset": other, "reference_genome": other_build}
    payload["_meta"]["next_commands"].insert(0, {"tool": ctx.tool_name, "arguments": recall})
    return error
