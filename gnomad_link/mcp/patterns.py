"""Shared MCP input-schema patterns and identifier helpers."""

from __future__ import annotations

import re

GENE_ID_PATTERN = r"^ENSG\d{11}$"
GENE_SYMBOL_PATTERN = r"^[A-Za-z0-9._-]{1,32}$"

# region / variant grammars used by the collapsed `target` auto-detectors.
REGION_TARGET_PATTERN = r"^(chr)?([1-9]|1[0-9]|2[0-2]|X|Y|M|MT)-\d+-\d+$"
VARIANT_TARGET_PATTERN = r"^(chr)?([1-9]|1\d|2[0-2]|X|Y|MT?)-\d+-[ACGT]+-[ACGT]+$"

_GENE_ID_RE = re.compile(GENE_ID_PATTERN)


def split_gene(gene: str) -> tuple[str | None, str | None]:
    """Return ``(gene_id, gene_symbol)`` for a single collapsed gene identifier.

    An ENSG-shaped value is a gene_id; anything else is treated as a symbol. This
    lets a tool expose ONE required ``gene`` parameter (with an ``examples`` the
    behaviour gate can build a valid call from) instead of two mutually-exclusive
    optional params that yield an unprobeable empty control call.
    """
    if _GENE_ID_RE.fullmatch(gene) or gene.upper().startswith("ENSG"):
        return gene, None
    return None, gene
