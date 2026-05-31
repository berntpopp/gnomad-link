"""Shared builders for _meta.next_commands entries.

Every tool emits next_commands in one shape: a list of {tool, arguments}
dicts whose arguments are directly callable (never empty). Centralising the
builders keeps the contract identical across tools.
"""

from __future__ import annotations

from typing import Any


def cmd(tool: str, **arguments: Any) -> dict[str, Any]:
    """One next_commands entry. Arguments must be directly callable (never empty)."""
    return {"tool": tool, "arguments": arguments}


def for_variant(variant_id: str, dataset: str) -> list[dict[str, Any]]:
    """Standard follow-ups for a resolved variant: frequencies then ClinVar."""
    return [
        cmd("get_variant_frequencies", variant_id=variant_id, dataset=dataset),
        cmd("get_clinvar_variant_details", variant_id=variant_id),
    ]
