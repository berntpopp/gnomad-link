"""Redirect mitochondrial ids sent to autosomal tools to get_mitochondrial_variant."""

from __future__ import annotations

from typing import Any

from gnomad_link.mcp.patterns import as_mito_variant_id

MITO_TOOL = "get_mitochondrial_variant"
MITO_RECOVERY = (
    "Mitochondrial (M-POS-REF-ALT) ids are not served by autosomal tools. Not a retry: "
    f"call {MITO_TOOL} with the same id."
)


class MitoIdRedirectError(ValueError):
    """Developer-authored message (no user values); carries the canonical mito id."""

    def __init__(self, variant_id: str) -> None:
        super().__init__("This is a mitochondrial variant id; autosomal tools do not serve chrM.")
        self.variant_id = variant_id


def redirect_validation_payload(payload: dict[str, Any], errors: list[Any]) -> None:
    """In place: point an arg-validation envelope at the mito tool if the input was a mito id."""
    mito_id = next((m for e in errors if (m := as_mito_variant_id(e.get("input")))), None)
    if not mito_id:
        return
    args = {"variant_id": mito_id}
    payload["message"] = "Invalid MCP arguments: this is a mitochondrial variant id."
    payload["recovery"] = MITO_RECOVERY
    payload["fallback_tool"], payload["fallback_args"] = MITO_TOOL, args
    payload["_meta"]["next_commands"].insert(0, {"tool": MITO_TOOL, "arguments": args})
