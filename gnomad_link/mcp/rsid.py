"""Accept an rsID on CHROM-POS-REF-ALT tools via the resolve_variant_id lookup (router #319)."""

from __future__ import annotations

import re
from typing import Any

from gnomad_link.mcp.errors import McpErrorContext, McpToolError, _provenance_meta
from gnomad_link.services import FrequencyService

RSID_PATTERN = r"rs\d+"  # length is capped by the tool's max_length
_RSID_RE = re.compile(RSID_PATTERN)


def _error(
    code: str, message: str, recovery: str, *, rsid: str, dataset: str, tool: str, **extra: Any
) -> McpToolError:
    args = {"query": rsid, "dataset": dataset}
    return McpToolError(
        {
            "success": False,
            "error_code": code,
            "message": message,
            "retryable": False,
            "recovery_action": "switch_tool",
            "fallback_tool": "resolve_variant_id",
            "fallback_args": args,
            "recovery": recovery,
            **extra,
            "_meta": {
                "tool": tool,
                "next_commands": [
                    {"tool": "resolve_variant_id", "arguments": args},
                    {"tool": "get_diagnostics", "arguments": {}},
                ],
                **_provenance_meta(McpErrorContext(tool_name=tool, dataset=dataset)),
            },
        }
    )


async def resolve_rsid(
    service: FrequencyService, variant_id: str, dataset: str, *, tool: str
) -> tuple[str, dict[str, str] | None]:
    """Return (canonical id, resolved_from); non-rsID input passes through unchanged."""
    if not _RSID_RE.fullmatch(variant_id):
        return variant_id, None
    ids = await service.search_variants(variant_id, dataset)
    if not ids:
        raise _error(
            "not_found",
            "No gnomAD variant matches this rsID in the requested dataset.",
            "Not a retry: try another dataset or call resolve_variant_id to verify the rsID.",
            rsid=variant_id,
            dataset=dataset,
            tool=tool,
        )
    if len(ids) > 1:
        # Multi-allelic rsID: several alleles share it; never pick one silently.
        raise _error(
            "ambiguous_query",
            "This rsID maps to several gnomAD variants (multi-allelic site).",
            "Pick one candidate variant_id and call this tool again with it; "
            "resolve_variant_id ranks the candidates with gene, consequence and AF.",
            rsid=variant_id,
            dataset=dataset,
            tool=tool,
            candidates=ids,
        )
    return ids[0], {"input": variant_id, "form": "rsid", "resolved_to": ids[0]}
