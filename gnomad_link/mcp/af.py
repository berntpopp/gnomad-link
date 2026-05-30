"""Allele-frequency source selection helpers."""

from __future__ import annotations

from typing import Any


def _value(source: Any, key: str) -> Any:
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def _af(source: Any) -> float | None:
    af = _value(source, "af")
    if isinstance(af, (int, float)) and not isinstance(af, bool):
        return float(af)
    ac = _value(source, "ac")
    an = _value(source, "an")
    if isinstance(ac, (int, float)) and isinstance(an, (int, float)) and an > 0:
        return float(ac / an)
    return None


def preferred_overall_af(exome: Any, genome: Any) -> tuple[float | None, str | None]:
    """Return the overall AF from the source with the largest called allele number."""
    best_an = -1
    best_af: float | None = None
    best_source: str | None = None
    for source_name, source in (("exome", exome), ("genome", genome)):
        af = _af(source)
        an = _value(source, "an")
        if af is None or not isinstance(an, (int, float)):
            continue
        if an > best_an:
            best_an = int(an)
            best_af = af
            best_source = source_name
    return best_af, best_source
