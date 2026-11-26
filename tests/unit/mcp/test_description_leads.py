"""D1 description leads (Tool-Schema Documentation Standard v1.1, rule 7).

Every tool description's first sentence must say what the tool returns, and the
fields a pinned tool's lead names must actually come back.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

# ponytail: copied from genefoundry-router scripts/surface.py (lead_states_return,
# router v0.13.1); re-vendor byte-identically if this repo ever vendors surface.py.
_LEAD_VERBS = (  # noqa: SIM905 - kept identical to the router copy
    "get fetch retrieve list look lookup search find resolve report read predict annotate "
    "compute calculate count summarize summarise map translate convert describe show check "
    "validate classify score rank query browse discover explain compare diff normalize normalise "
    "expand evaluate assess enumerate identify locate export download match suggest recommend "
    "inspect generate render estimate"
).split()
_VERB_LEAD = re.compile(
    rf"^(?:use this (?:tool )?to )?(?:{'|'.join(_LEAD_VERBS)})(?:s|es|ies)?\b", re.IGNORECASE
)
_RETURNS = re.compile(
    r"(?<!not )(?<!n't )(?<!n’t )(?<!never )\breturn(?:s|ed|ing)?\b(?!\s*[~<\d])|→|->",  # noqa: RUF001
    re.IGNORECASE,
)
_FIELD_LIST = re.compile(r"\w+\W+\w+[^:]*:\s+[^.;:]+,")
_SENTENCE_END = re.compile(r"(?<!e\.g\.)(?<!i\.e\.)(?<=[.!?])\s+")


def _lead_states_return(description: str | None) -> bool:
    text = " ".join((description or "").split())
    lead = _SENTENCE_END.split(text, maxsplit=1)[0][:300]
    return bool(_VERB_LEAD.match(lead) or _RETURNS.search(lead) or _FIELD_LIST.search(lead))


@pytest.mark.asyncio
async def test_every_tool_description_lead_states_what_it_returns(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    tools = await create_gnomad_mcp(service_factory=fake_service_factory).list_tools()
    offenders = [t.name for t in tools if not _lead_states_return(t.description)]
    assert offenders == [], f"D1: first sentence must say what is returned: {offenders}"


class _StubGeneVariantsService:
    async def get_gene_with_variants(self, gene: str, dataset: str) -> dict[str, Any]:
        pops = [{"id": "nfe", "ac": 2, "an": 1000}]
        variants = [
            {
                "variant_id": "17-43045711-G-A",
                "consequence": "missense_variant",
                "hgvsc": "c.5000C>T",
                "hgvsp": "p.Ala1667Val",
                "exome": {"ac": 2, "an": 1000, "af": 0.002, "populations": pops},
                "genome": None,
            }
        ]
        return {"gene_id": "ENSG00000012048", "symbol": "BRCA1", "variants": variants}


@pytest.mark.asyncio
async def test_get_gene_variants_returns_the_fields_its_lead_names() -> None:
    """Lead: "returns each variant's id, consequence, HGVS, and AC/AN/AF"."""
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubGeneVariantsService()
    mcp = create_gnomad_mcp(service_factory=lambda: stub)
    tools = {t.name: t for t in await mcp.list_tools()}
    assert "returns each variant's id, consequence, HGVS, and AC/AN/AF" in (
        tools["get_gene_variants"].description or ""
    )

    result = await mcp.call_tool("get_gene_variants", {"gene_id": "ENSG00000012048"})
    row = (result.structured_content or {})["result"]["variants"][0]

    assert {"variant_id", "consequence", "hgvsc", "hgvsp"} <= row.keys()
    assert {"ac", "an", "af"} <= row["exome"].keys()
