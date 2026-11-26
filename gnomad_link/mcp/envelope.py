"""The success frame and per-call ``_meta`` of the Response-Envelope Standard (v1, v1.2)."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from gnomad_link.mcp.resources import GNOMAD_DATA_RELEASE


def build_envelope(payload: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    """Frame a tool body's dict as ``{success, result|results, _meta}`` (v1 section 1).

    A body that names neither ``result`` nor ``results`` is the single-item payload and
    goes under ``result``. ``meta`` is merged over any ``_meta`` the body set itself.
    """
    own_meta: dict[str, Any] = payload.pop("_meta", None) or {}
    success = payload.pop("success", True)
    if success and isinstance(payload.get("has_more"), bool) and "total_count" in payload:
        # v1 section 5. These tools page by `limit` only: there is no cursor, a wider
        # `limit` or a narrower query gets the rest. The top-level copies stay.
        own_meta["pagination"] = {
            "total_count": payload["total_count"],
            "has_more": payload["has_more"],
            "next_cursor": None,
        }
    if success and not {"result", "results"} & payload.keys():
        payload = {"result": payload}
    return {"success": success, **payload, "_meta": {**own_meta, **meta}}


def stamp(
    envelope: dict[str, Any], started: float, fetch_times: list[float] | None = None
) -> dict[str, Any]:
    """Set the measured ``_meta.elapsed_ms`` and, on a success, the v1.2 provenance.

    A success passes ``fetch_times``: ``retrieved_at`` is the oldest upstream fetch behind
    the result, so a cache hit keeps the time of the fetch that filled the entry. A
    result computed without any fetch dates to the call.
    """
    meta = envelope.setdefault("_meta", {})
    meta["elapsed_ms"] = round((time.time() - started) * 1000)
    if fetch_times is not None:
        fetched_at = datetime.fromtimestamp(min(fetch_times, default=started), UTC)
        meta["source"] = "gnomad"
        meta["data_version"] = GNOMAD_DATA_RELEASE
        meta["retrieved_at"] = fetched_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    return envelope
