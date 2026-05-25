# MCP Facade Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace OpenAPI-derived MCP tools with a hand-authored, LLM-first MCP facade while preserving the existing REST API and HTTP mount.

**Architecture:** Keep FastAPI/OpenAPI as the REST/debug facade. Add `gnomad_link.mcp` as a separate MCP facade over the existing service/client layer, following the active `pubtator-link` structure but without PubTator's profile/RAG complexity.

**Tech Stack:** Python 3.12, FastMCP, MCP `ToolAnnotations`, FastAPI, Pydantic v2, pytest, Ruff, mypy.

---

### Task 1: Lock Current MCP Surface Expectations

**Files:**
- Create: `tests/unit/mcp/test_mcp_facade_surface.py`
- Modify: `tests/unit/test_server_manager.py`

- [ ] **Step 1: Write the failing MCP surface tests**

Create `tests/unit/mcp/test_mcp_facade_surface.py`:

```python
from __future__ import annotations

import re

import pytest

ANTHROPIC_TOOL_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

EXPECTED_TOOLS = {
    "get_server_capabilities",
    "get_variant_frequencies",
    "get_variant_details",
    "get_gene_details",
    "get_gene_variants",
    "get_clinvar_variant_details",
    "get_clinvar_meta",
    "liftover_variant",
    "get_structural_variant",
    "get_mitochondrial_variant",
    "get_region",
    "get_transcript_details",
    "search_genes",
    "search_variants",
}


def _service_factory():
    raise AssertionError("surface tests must not call live services")


@pytest.mark.asyncio
async def test_create_gnomad_mcp_exposes_expected_tool_names() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=_service_factory)
    tool_names = {tool.name for tool in await mcp.list_tools()}

    assert EXPECTED_TOOLS <= tool_names
    assert "clear_cache" not in tool_names
    assert "get_structural_variants" not in tool_names


@pytest.mark.asyncio
async def test_all_tool_names_match_anthropic_remote_mcp_regex() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=_service_factory)
    offenders = [
        tool.name
        for tool in await mcp.list_tools()
        if not ANTHROPIC_TOOL_NAME_RE.fullmatch(tool.name)
    ]

    assert offenders == []


def test_server_instructions_include_workflows_and_safety() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    instructions = create_gnomad_mcp(service_factory=_service_factory).instructions or ""

    assert "Variant frequency" in instructions
    assert "get_server_capabilities" in instructions
    assert "gnomad://capabilities" in instructions
    assert "Research use only" in instructions
    assert len(instructions) < 1200
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run:

```bash
uv run pytest tests/unit/mcp/test_mcp_facade_surface.py -q
```

Expected: fails because `gnomad_link.mcp.facade` does not exist yet.

- [ ] **Step 3: Update the existing server-manager grep test**

In `tests/unit/test_server_manager.py`, replace the source assertion that
expects `FastMCP.from_fastapi` with assertions that `create_mcp_server()` calls
`create_gnomad_mcp(service_factory=service_factory)`, no longer takes a FastAPI `app`
parameter, and no longer defines `mcp_custom_names`.

- [ ] **Step 4: Run the updated focused tests and confirm failure**

Run:

```bash
uv run pytest tests/unit/mcp/test_mcp_facade_surface.py tests/unit/test_server_manager.py -q
```

Expected: failures describe missing facade and old server-manager code.

### Task 2: Add MCP Facade Skeleton, Instructions, And Capabilities

**Files:**
- Create: `gnomad_link/mcp/__init__.py`
- Create: `gnomad_link/mcp/annotations.py`
- Create: `gnomad_link/mcp/resources.py`
- Create: `gnomad_link/mcp/facade.py`
- Modify: `gnomad_link/server_manager.py`
- Test: `tests/unit/mcp/test_mcp_facade_surface.py`
- Test: `tests/unit/test_server_manager.py`

- [ ] **Step 1: Add shared annotation constants**

Create `gnomad_link/mcp/annotations.py`:

```python
from __future__ import annotations

from mcp.types import ToolAnnotations

READ_ONLY_OPEN_WORLD = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)

READ_ONLY_CLOSED_WORLD = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
```

- [ ] **Step 2: Add capabilities resources**

Create `gnomad_link/mcp/resources.py` with:

```python
from __future__ import annotations

from typing import Any

RESEARCH_USE_NOTICE = "Research use only; not for clinical decision support."


def get_capabilities_resource() -> dict[str, Any]:
    return {
        "server": "gnomad-link",
        "research_use_only": True,
        "datasets": {
            "gnomad_r2_1": {"reference_genome": "GRCh37"},
            "gnomad_r3": {"reference_genome": "GRCh38"},
            "gnomad_r4": {"reference_genome": "GRCh38", "default": True},
        },
        "sv_datasets": ["gnomad_sv_r2_1", "gnomad_sv_r4"],
        "population_codes": [
            "afr",
            "amr",
            "asj",
            "eas",
            "fin",
            "nfe",
            "sas",
            "mid",
            "ami",
            "remaining",
        ],
        "population_suffixes": {
            "_XX": "sex-split XX population row when present",
            "_XY": "sex-split XY population row when present",
        },
        "recommended_workflows": [
            "variant_id -> get_variant_frequencies",
            "rsID or loose text -> search_variants -> get_variant_frequencies",
            "gene symbol -> search_genes -> get_gene_details",
            "clinical annotation -> get_clinvar_variant_details + get_variant_frequencies",
            "build conversion -> liftover_variant",
        ],
        "tools": [
            "get_server_capabilities",
            "get_variant_frequencies",
            "get_variant_details",
            "get_gene_details",
            "get_gene_variants",
            "get_clinvar_variant_details",
            "get_clinvar_meta",
            "liftover_variant",
            "get_structural_variant",
            "get_mitochondrial_variant",
            "get_region",
            "get_transcript_details",
            "search_genes",
            "search_variants",
        ],
        "limitations": [
            "Default local CI avoids live gnomAD calls.",
            "Large region and gene-variant calls should use limits or compact modes.",
            RESEARCH_USE_NOTICE,
        ],
    }


def get_usage_resource() -> str:
    return (
        "# gnomAD Link MCP Usage\n\n"
        "Use CHROM-POS-REF-ALT variant IDs for SNV/indel frequencies. "
        "Use M-POS-REF-ALT for mitochondrial variants. Prefer compact defaults "
        "for LLM workflows and request full payloads only for debugging.\n\n"
        f"{RESEARCH_USE_NOTICE}"
    )
```

- [ ] **Step 3: Add the facade skeleton**

Create `gnomad_link/mcp/facade.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP

from gnomad_link.services import FrequencyService
from gnomad_link.mcp.annotations import READ_ONLY_CLOSED_WORLD
from gnomad_link.mcp.resources import (
    RESEARCH_USE_NOTICE,
    get_capabilities_resource,
    get_usage_resource,
)
from gnomad_link.mcp.tools import register_gnomad_tools


def create_gnomad_mcp(
    service_factory: Callable[[], FrequencyService],
) -> FastMCP:
    mcp = FastMCP(
        name="gnomad-link",
        instructions=(
            "gnomAD Link grounds population-genetics work in gnomAD datasets.\n"
            "- Variant frequency: get_variant_frequencies for CHROM-POS-REF-ALT; "
            "search_variants first for rsIDs or loose text.\n"
            "- Clinical annotation: pair get_clinvar_variant_details with "
            "get_variant_frequencies.\n"
            "- Gene constraint: search_genes then get_gene_details.\n"
            "- Coordinates: liftover_variant converts between GRCh37 and GRCh38.\n"
            "- Special variants: get_structural_variant for SVs; "
            "get_mitochondrial_variant for M-POS-REF-ALT.\n"
            "- Datasets: gnomad_r2_1 is GRCh37; gnomad_r3 and gnomad_r4 are "
            "GRCh38; gnomad_r4 is default.\n"
            "- Discovery: call get_server_capabilities or read "
            f"gnomad://capabilities. {RESEARCH_USE_NOTICE}"
        ),
    )

    register_metadata(mcp)
    register_gnomad_tools(mcp, service_factory=service_factory)
    return mcp


def register_metadata(mcp: FastMCP) -> None:
    @mcp.tool(
        name="get_server_capabilities",
        title="Get gnomAD Link Capabilities",
        annotations=READ_ONLY_CLOSED_WORLD,
    )
    async def get_server_capabilities() -> dict[str, Any]:
        """Use this when a client needs supported tools, datasets, populations, workflows, and limitations."""

        return get_capabilities_resource()

    @mcp.resource("gnomad://capabilities")
    def capabilities() -> dict[str, Any]:
        return get_capabilities_resource()

    @mcp.resource("gnomad://usage")
    def usage() -> str:
        return get_usage_resource()
```

- [ ] **Step 4: Add a service factory helper in the server manager**

In `gnomad_link/server_manager.py`, import `create_gnomad_mcp` and add a helper
that creates one direct service for stdio mode:

```python
def _create_frequency_service(self) -> FrequencyService:
    api_client = UnifiedGnomadClient()
    return FrequencyService(
        client=api_client,
        cache_size=settings.CACHE_SIZE,
        cache_ttl_minutes=settings.CACHE_TTL_MINUTES,
    )
```

- [ ] **Step 5: Point the server manager at the facade**

Replace `create_mcp_server(self, app: FastAPI, config: ServerConfig)` with
`create_mcp_server(self, config: ServerConfig, service_factory:
Callable[[], FrequencyService])`. Its body should be:

```python
try:
    mcp = create_gnomad_mcp(service_factory=service_factory)
    self.logger.info("MCP server created successfully")
    return mcp
except Exception as e:
    raise MCPIntegrationError(f"Failed to create MCP server: {e}", "mcp") from e
```

Remove the `FastMCP.from_fastapi()` route-map and `mcp_custom_names` code.

- [ ] **Step 6: Wire unified and stdio service ownership**

In unified mode, create the FastAPI app as today and pass a lazy factory that
reads app state at tool-call time:

```python
def service_factory() -> FrequencyService:
    if self.app is None:
        raise RuntimeError("FastAPI app is not initialized")
    return self.app.state.frequency_service

self.mcp = await self.create_mcp_server(config, service_factory)
```

In stdio mode, stop creating the FastAPI app only for MCP introspection. Create
one service directly and pass it into the facade:

```python
service = self._create_frequency_service()
self.mcp = await self.create_mcp_server(config, lambda: service)
```

Remove the stdio-only call to `_initialize_app_state()` if it becomes unused.

- [ ] **Step 7: Run focused tests**

Run:

```bash
uv run pytest tests/unit/mcp/test_mcp_facade_surface.py tests/unit/test_server_manager.py -q
```

Expected: metadata/instruction tests pass; expected data tool tests still fail
until Task 3 registers the 13 data tools.

### Task 3: Register Parity MCP Data Tools

**Files:**
- Create: `gnomad_link/mcp/tools.py`
- Modify: `gnomad_link/mcp/facade.py`
- Test: `tests/unit/mcp/test_mcp_facade_surface.py`

- [ ] **Step 1: Add tool-registration module**

Create `gnomad_link/mcp/tools.py` with one `register_gnomad_tools(mcp: FastMCP,
service_factory: Callable[[], FrequencyService]) -> None` function. Register
all 13 existing public MCP tool names with the same default arguments the
FastAPI-derived surface currently exposes.

Each tool should:

- use `annotations=READ_ONLY_OPEN_WORLD`
- acquire a `FrequencyService` by calling `service_factory()` inside the tool
  body, not at registration time
- call `service.get_variant_frequencies`, `service.get_gene`,
  `service.search_genes`, and `service.search_variants` where those service
  methods exist
- call `service.client.*` for parity routes that currently bypass a service
  wrapper, including region, transcript, structural variant, mitochondrial,
  ClinVar, ClinVar metadata, gene variants, variant details, and liftover
- preserve current tool names
- use an LLM-oriented docstring that cross-references sibling tools

The first pass may return the same raw shapes as REST to preserve parity.
The `search_variants` description must state that parity phase returns variant
IDs only and callers should follow with `get_variant_frequencies` or
`get_variant_details`.

- [ ] **Step 2: Wire data tools into facade**

In `gnomad_link/mcp/facade.py`, import and call:

```python
from gnomad_link.mcp.tools import register_gnomad_tools

register_metadata(mcp)
register_gnomad_tools(mcp, service_factory=service_factory)
```

- [ ] **Step 3: Run parity tests**

Run:

```bash
uv run pytest tests/unit/mcp/test_mcp_facade_surface.py -q
```

Expected: all expected tool names are present and all names pass the Anthropic
regex guard.

- [ ] **Step 4: Add annotation assertions**

Extend `tests/unit/mcp/test_mcp_facade_surface.py` with:

```python
@pytest.mark.asyncio
async def test_data_tools_are_read_only_open_world() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    tool_by_name = {
        tool.name: tool
        for tool in await create_gnomad_mcp(service_factory=_service_factory).list_tools()
    }
    for name in EXPECTED_TOOLS - {"get_server_capabilities"}:
        annotations = tool_by_name[name].annotations
        assert annotations is not None
        assert annotations.readOnlyHint is True
        assert annotations.destructiveHint is False
        assert annotations.idempotentHint is True
        assert annotations.openWorldHint is True
```

Run the focused test again and fix any missing annotations.

### Task 4: Verify Population IDs And Add Compact Frequency Response Shaping

**Files:**
- Create: `gnomad_link/mcp/shaping.py`
- Modify: `gnomad_link/mcp/tools.py`
- Create: `tests/unit/mcp/test_frequency_shaping.py`
- Modify: `tests/unit/mcp/test_mcp_facade_surface.py`

- [ ] **Step 1: Run a live population-ID verification spike**

Run one explicit live integration check outside default CI and record the
observed population IDs in the implementation notes or test fixture comments:

```bash
uv run python - <<'PY'
import asyncio
from gnomad_link.api.client import UnifiedGnomadClient
from gnomad_link.services.frequency_service import FrequencyService

async def main() -> None:
    service = FrequencyService(client=UnifiedGnomadClient())
    response = await service.get_variant_frequencies("1-55051215-G-GA", "gnomad_r4")
    for source_name in ("exome", "genome"):
        source = getattr(response, source_name)
        if source is not None:
            print(source_name, [pop.name for pop in source.populations])

asyncio.run(main())
PY
```

If a gnomAD dataset returns subcohort-style IDs, codify the actual prefixes or
patterns in tests. If no subcohort IDs are observed, keep `include_subcohorts`
documented as reserved for datasets that expose non-population subgroup IDs and
test only observed sex-split and zero-population behavior.

- [ ] **Step 2: Write shaping tests**

Create tests proving:

- zero-AC populations are omitted by default
- observed non-population subgroup IDs are omitted unless
  `include_subcohorts=True`, or `include_subcohorts` is documented as currently
  inert when the spike finds no such IDs
- `_XX` and `_XY` populations are omitted unless `include_sex_split=True`
- `populations=["afr", "nfe"]` filters to selected base population IDs
- each returned source and population includes `af`

- [ ] **Step 3: Implement frequency shaping helper**

Create a pure helper:

```python
def shape_variant_frequencies(
    response: Any,
    *,
    populations: list[str] | None,
    include_subcohorts: bool,
    include_sex_split: bool,
    exclude_zero_populations: bool,
) -> dict[str, Any]:
    """Return the MCP compact frequency payload for one variant."""
```

It should accept a `VariantFrequencyResponse` or a dict and return a JSON-safe
dict with `variant_id`, `dataset`, `exome`, `genome`, and `truncated` metadata
when filtering removes rows.

- [ ] **Step 4: Update MCP `get_variant_frequencies` only**

Add MCP-only parameters:

```python
populations: list[str] | None = None
include_subcohorts: bool = False
include_sex_split: bool = False
exclude_zero_populations: bool = True
```

Do not change the REST route in this task.

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/unit/mcp/test_frequency_shaping.py tests/unit/mcp/test_mcp_facade_surface.py -q
```

Expected: pass.

### Task 5: Add MCP Limits And Compact Modes For Large Tools

**Files:**
- Modify: `gnomad_link/mcp/shaping.py`
- Modify: `gnomad_link/mcp/tools.py`
- Create: `tests/unit/mcp/test_large_response_shaping.py`

- [ ] **Step 1: Write tests for gene-variant limiting**

Test that `get_gene_variants` defaults to `limit=100`, supports lower limits,
filters by `consequence`, filters by `max_af`, filters by `min_ac`, and reports
`truncated=True` when more variants were available.

- [ ] **Step 2: Implement gene-variant shaping**

Add a pure helper that filters the list returned by `client.get_gene_variants()`
without changing GraphQL yet.

- [ ] **Step 3: Write tests for variant-details compact mode**

Test that `response_mode="compact"` returns key fields such as `variant_id`,
`rsids`, `major_consequence`, canonical transcript consequence when present,
ClinVar-like clinical fields when present, and frequency summaries when present.
Test that `response_mode="full"` returns the raw client response.

- [ ] **Step 4: Implement variant-details compact shaping**

Add `response_mode: Literal["compact", "full"] = "compact"` to the MCP tool
only and route through the shaping helper.

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/unit/mcp/test_large_response_shaping.py -q
```

Expected: pass.

### Task 6: Add MCP Client Smoke Test

**Files:**
- Create: `tests/unit/mcp/test_mcp_client_smoke.py`

- [ ] **Step 1: Write in-process client smoke test**

Use FastMCP's in-process client to list tools and call
`get_server_capabilities`. Also read `gnomad://capabilities` through
`await mcp.read_resource("gnomad://capabilities")` or the FastMCP in-process
client and assert the payload contains `datasets`, `tools`, and
`recommended_workflows`.

- [ ] **Step 2: Run smoke test**

Run:

```bash
uv run pytest tests/unit/mcp/test_mcp_client_smoke.py -q
```

Expected: pass without network access.

### Task 7: Update Docs For The New MCP Architecture

**Files:**
- Modify: `README.md`
- Modify: `docs/MCP_CONNECTION_GUIDE.md`
- Modify: `docs/api-reference.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Document MCP as hand-authored facade**

Update docs to say FastAPI/OpenAPI remains the REST surface and MCP is
hand-authored in `gnomad_link/mcp/`.

- [ ] **Step 2: Update tool list**

List the 14 MCP tools, including `get_server_capabilities`, and keep the
Claude Code command:

```bash
claude mcp add --transport http gnomad-link http://127.0.0.1:8020/mcp
```

- [ ] **Step 3: Update agent guidance**

In `AGENTS.md`, add that MCP tool names, schemas, resources, and response modes
are owned by `gnomad_link/mcp/`, not by FastAPI route metadata.

### Task 8: Full Verification And Commit

**Files:**
- All modified files

- [ ] **Step 1: Format**

Run:

```bash
make format
```

- [ ] **Step 2: Run local CI**

Run:

```bash
make ci-local
```

Expected: formatting, Ruff, line-budget, mypy, and unit tests pass.

- [ ] **Step 3: Rebuild and smoke Docker MCP**

Run:

```bash
make docker-build
make docker-up
curl -fsS http://127.0.0.1:8020/health
```

Then list MCP tools using the existing Python MCP client smoke snippet or
`claude mcp list`.

- [ ] **Step 4: Commit**

Commit the completed implementation:

```bash
git add gnomad_link tests README.md docs AGENTS.md
git commit -m "feat: add hand-authored gnomad mcp facade"
```
