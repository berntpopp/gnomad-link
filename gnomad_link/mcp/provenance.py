"""Single source of truth for carrier-tool provenance (citations + assumptions).

The carrier tools used to embed a byte-identical citation list and a
multi-sentence assumptions note in EVERY response. That static prose is the
textbook case for dedup-via-resource (Anthropic, *Effective context
engineering*): keep a short, self-sufficient pointer inline and expose the
verbose text once as a stable resource (``gnomad://citations``).

Contract, gated on the existing ``response_mode`` lever:

- compact (default): SHORT author-year citations + a one-sentence assumptions
  clause + a ``citations_ref`` pointer. Groundable standalone (no second fetch
  required) while ~400 bytes lighter per call.
- full: the complete bibliographic citations + full assumptions prose + the
  same pointer.

The short forms intentionally retain the load-bearing tokens
("Hardy-Weinberg", "Schrodi", "Karczewski") so a claim is never uncited.
"""

from __future__ import annotations

from typing import Any

from gnomad_link.mcp.resources import GNOMAD_DATA_RELEASE, RESEARCH_USE_NOTICE

#: Stable URI of the full citation/assumptions registry resource.
CITATIONS_REF = "gnomad://citations"

# --- Full bibliographic prose (verbatim from the pre-dedup tools) ------------

_VARIANT_CARRIER_CITATIONS_FULL: tuple[str, ...] = (
    "Schrodi et al. 2015, Hum Genet, doi:10.1007/s00439-015-1551-8 "
    "(2pq/q^2 carrier framework + CI concept)",
    "Karczewski et al. 2020, Nature (gnomAD allele-frequency reference)",
    "Guo et al. 2019; Zhu et al. 2022 (homozygote-corrected variant carrier rate)",
    "Hotakainen et al. 2025; Kandolin et al. 2024 (X-linked sex-split estimation)",
)
_VARIANT_CARRIER_ASSUMPTIONS_FULL = (
    "Estimates assume Hardy-Weinberg equilibrium, random mating, complete "
    "penetrance, and a single causal variant. Frequencies are a minimum "
    "estimate from one gnomAD variant and are unsafe for clinical use."
)

_GENE_CARRIER_CITATIONS_FULL: tuple[str, ...] = (
    "Karczewski et al. 2022 (PMC9763236) - variant/gene carrier rate.",
    "Schrodi et al. 2015, Hum Genet, doi:10.1007/s00439-015-1551-8 - 2pq carrier framework.",
    "Karczewski et al. 2020, Nature - gnomAD allele frequencies.",
)
_GENE_CARRIER_ASSUMPTIONS_FULL = (
    "Gene-level estimate: sums qualifying pathogenic variants under Hardy-Weinberg "
    "equilibrium (random mating, complete penetrance unless penetrance<1). Carrier "
    "frequency uses the selected method (hom_exclusion=GCR is the default). A minimum "
    "estimate bounded by gnomAD ascertainment and ClinVar completeness; not clinical "
    "decision support."
)

# --- Short, inline-by-default forms (groundable without dereferencing) -------

_VARIANT_CARRIER_CITATIONS_SHORT: tuple[str, ...] = (
    "Schrodi 2015",
    "Karczewski 2020",
    "Guo 2019; Zhu 2022",
    "Hotakainen 2025; Kandolin 2024",
)
_VARIANT_CARRIER_ASSUMPTIONS_SHORT = (
    "Assumes Hardy-Weinberg equilibrium, random mating, complete penetrance, and one "
    "causal variant; a minimum estimate from a single gnomAD variant. Research use only."
)

_GENE_CARRIER_CITATIONS_SHORT: tuple[str, ...] = (
    "Karczewski 2022",
    "Schrodi 2015",
    "Karczewski 2020",
)
_GENE_CARRIER_ASSUMPTIONS_SHORT = (
    "Gene-level minimum estimate: sums qualifying pathogenic variants under "
    "Hardy-Weinberg equilibrium; bounded by gnomAD ascertainment and ClinVar "
    "completeness. Research use only."
)

_REGISTRY: dict[str, dict[str, Any]] = {
    "variant_carrier": {
        "citations_full": _VARIANT_CARRIER_CITATIONS_FULL,
        "citations_short": _VARIANT_CARRIER_CITATIONS_SHORT,
        "assumptions_full": _VARIANT_CARRIER_ASSUMPTIONS_FULL,
        "assumptions_short": _VARIANT_CARRIER_ASSUMPTIONS_SHORT,
    },
    "gene_carrier": {
        "citations_full": _GENE_CARRIER_CITATIONS_FULL,
        "citations_short": _GENE_CARRIER_CITATIONS_SHORT,
        "assumptions_full": _GENE_CARRIER_ASSUMPTIONS_FULL,
        "assumptions_short": _GENE_CARRIER_ASSUMPTIONS_SHORT,
    },
}


def provenance_block(topic: str, *, full: bool) -> dict[str, Any]:
    """Return the inline provenance block for ``topic`` (variant_carrier|gene_carrier).

    ``full=True`` inlines the complete prose; otherwise the short, still-cited
    form. Both carry ``citations_ref`` pointing at the ``gnomad://citations``
    resource that holds the complete registry.
    """
    entry = _REGISTRY[topic]
    citations = entry["citations_full"] if full else entry["citations_short"]
    assumptions = entry["assumptions_full"] if full else entry["assumptions_short"]
    return {
        "assumptions_note": assumptions,
        "citations": list(citations),
        "citations_ref": CITATIONS_REF,
    }


def get_citations_resource() -> dict[str, Any]:
    """Full citation/assumptions registry exposed at ``gnomad://citations``.

    Read once by an LLM and cached by URI; results carry only ``citations_ref``.
    """
    return {
        "schema": "gnomad-link/citations/v1",
        "gnomad_release": GNOMAD_DATA_RELEASE,
        "research_use_only": True,
        "notice": RESEARCH_USE_NOTICE,
        "topics": {
            topic: {
                "assumptions_note": entry["assumptions_full"],
                "citations": list(entry["citations_full"]),
            }
            for topic, entry in _REGISTRY.items()
        },
    }
