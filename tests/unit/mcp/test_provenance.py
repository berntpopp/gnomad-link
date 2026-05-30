"""Carrier provenance: short-inline-by-default citations + a gnomad://citations pointer.

Compact mode keeps groundability (no second fetch needed) by inlining short
author-year citations and a one-sentence assumptions note that still names the
load-bearing tokens; full mode inlines the complete bibliographic prose. Both
carry citations_ref.
"""

from __future__ import annotations

import pytest

from gnomad_link.mcp.provenance import (
    CITATIONS_REF,
    get_citations_resource,
    provenance_block,
)


@pytest.mark.parametrize("topic", ["variant_carrier", "gene_carrier"])
def test_block_always_carries_citations_ref(topic: str) -> None:
    for full in (False, True):
        block = provenance_block(topic, full=full)
        assert block["citations_ref"] == CITATIONS_REF == "gnomad://citations"
        assert block["assumptions_note"]
        assert isinstance(block["citations"], list) and block["citations"]


def test_compact_is_lighter_than_full() -> None:
    compact = provenance_block("variant_carrier", full=False)
    full = provenance_block("variant_carrier", full=True)
    compact_bytes = len(str(compact["citations"])) + len(compact["assumptions_note"])
    full_bytes = len(str(full["citations"])) + len(full["assumptions_note"])
    assert compact_bytes < full_bytes


def test_short_forms_preserve_grounding_tokens() -> None:
    # Variant carrier: short assumptions must still say Hardy-Weinberg; short
    # citations must still name Schrodi (the carrier-framework source).
    v = provenance_block("variant_carrier", full=False)
    assert "Hardy-Weinberg" in v["assumptions_note"]
    assert any("Schrodi" in c for c in v["citations"])
    # Gene carrier: short citations must still name Karczewski.
    g = provenance_block("gene_carrier", full=False)
    assert "Hardy-Weinberg" in g["assumptions_note"]
    assert any("Karczewski" in c for c in g["citations"])


def test_full_inlines_complete_bibliographic_prose() -> None:
    full = provenance_block("variant_carrier", full=True)
    # The full form carries DOIs / journal detail the short form omits.
    assert any("doi:" in c for c in full["citations"])


def test_citations_resource_holds_full_registry() -> None:
    res = get_citations_resource()
    assert res["gnomad_release"]
    assert res["research_use_only"] is True
    topics = res["topics"]
    assert set(topics) == {"variant_carrier", "gene_carrier"}
    for entry in topics.values():
        assert entry["assumptions_note"]
        assert entry["citations"]
    # The resource holds the FULL prose (with DOIs), matching full-mode blocks.
    assert any("doi:" in c for c in topics["variant_carrier"]["citations"])
