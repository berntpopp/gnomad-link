# MCP Facade Migration Implementation Plan

> Historical record

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `FastMCP.from_fastapi()` auto-derivation with a hand-authored MCP-first facade modelled on `pubtator-link`. MCP becomes the primary interface; REST is reduced to a minimal `/health` shim for Docker. The migration fixes the silent population truncation bug, adds structured error envelopes, output schemas, tool annotations, response shaping, and a unified `run_mcp_tool` wrapper.

**Architecture:** A new `gnomad_link/mcp/` package owns the FastMCP server. Tools are explicitly registered in topical modules and dispatch through service-layer methods that previously only the routes called. The FastAPI app is kept *only* as a thin host for the mounted MCP HTTP app plus a single `/health` route; all `/variant`, `/gene`, etc. REST routes are deleted, along with the corresponding integration tests. Cache management moves to a CLI-only helper. Error handling, response shaping, and capabilities resources follow `pubtator_link/mcp/` patterns verbatim where transferable.

**Tech Stack:** Python 3.12, FastMCP (>=2.x), MCP `ToolAnnotations`/`outputSchema`, FastAPI (host only), Pydantic v2 (`Annotated` + `Field`), pytest, pytest-asyncio, Ruff, mypy.

---

## Pre-Flight Reading

Before starting Task 1, the executor must read these source files to load context:

- `/home/bernt-popp/development/pubtator-link/pubtator_link/mcp/facade.py` — reference facade
- `/home/bernt-popp/development/pubtator-link/pubtator_link/mcp/annotations.py` — annotation constants
- `/home/bernt-popp/development/pubtator-link/pubtator_link/mcp/errors.py` — error envelope and `run_mcp_tool`
- `/home/bernt-popp/development/pubtator-link/pubtator_link/mcp/resources.py` — capabilities/usage resources
- `/home/bernt-popp/development/pubtator-link/pubtator_link/mcp/tools/discovery.py` — sample tool registration
- `/home/bernt-popp/development/gnomad-link/gnomad_link/server_manager.py` — current FastMCP.from_fastapi wiring (to be replaced)
- `/home/bernt-popp/development/gnomad-link/gnomad_link/services/frequency_service.py` — extant service layer
- `/home/bernt-popp/development/gnomad-link/gnomad_link/api/client.py` — `UnifiedGnomadClient` public methods

---

## Final MCP Tool Surface (15 tools)

| Tool | Notes |
|---|---|
| `get_server_capabilities` | Metadata; closed-world annotation |
| `get_variant_frequencies` | Adds `populations`, `include_subcohorts`, `include_sex_split`, `exclude_zero_populations` |
| `get_variant_details` | Adds `response_mode: "compact" \| "full" = "compact"` |
| `get_gene_details` | Typed `Gene` output; cross-references `get_gene_variants` |
| `get_gene_variants` | Adds `limit ≤ 500`, `consequence`, `max_af`, `min_ac` |
| `get_clinvar_variant_details` | Typed `ClinVarVariant` output |
| `get_clinvar_meta` | Parity tool; trivial payload |
| `liftover_variant` | Typed `LiftoverResponse` output |
| `get_structural_variant` | Typed `StructuralVariant` output |
| `get_mitochondrial_variant` | Typed `MitochondrialVariant` output |
| `get_region` | Adds `max_bp_span ≤ 100_000`, `limit`, `include_clinvar`, `include_genes` |
| `get_transcript_details` | New `Transcript` Pydantic model |
| `search_genes` | Adds `limit ≤ 50` |
| `resolve_variant_id` | Renamed from `search_variants`; description leads with "Returns IDs only" |
| `search_variants` | Deprecated alias kept for one release; delegates to `resolve_variant_id` and emits a `_meta.deprecated` notice |

**Removed REST routes:** all `/variant`, `/gene`, `/clinvar`, `/liftover`, `/structural-variant`, `/mitochondrial-variant`, `/region`, `/transcript`, `/search/*`, `/cache/*`, `/` (root info). **Kept:** `/health` only.

---

## File Structure

| Path | Role |
|---|---|
| `gnomad_link/mcp/__init__.py` | Package marker; re-exports `create_gnomad_mcp` |
| `gnomad_link/mcp/facade.py` | Factory `create_gnomad_mcp(service_factory)`; installs handlers |
| `gnomad_link/mcp/annotations.py` | `READ_ONLY_OPEN_WORLD`, `READ_ONLY_CLOSED_WORLD` |
| `gnomad_link/mcp/errors.py` | `mcp_tool_error`, `run_mcp_tool`, `install_validation_error_handler`, recent-error ring |
| `gnomad_link/mcp/resources.py` | `get_capabilities_resource`, `get_usage_resource` |
| `gnomad_link/mcp/shaping.py` | `shape_variant_frequencies`, `shape_variant_details`, `shape_gene_variants`, `shape_region` |
| `gnomad_link/mcp/tools/__init__.py` | `register_gnomad_tools(mcp, service_factory)` dispatcher |
| `gnomad_link/mcp/tools/metadata.py` | `get_server_capabilities` tool + resources |
| `gnomad_link/mcp/tools/variants.py` | `get_variant_frequencies`, `get_variant_details` |
| `gnomad_link/mcp/tools/genes.py` | `get_gene_details`, `get_gene_variants` |
| `gnomad_link/mcp/tools/clinvar.py` | `get_clinvar_variant_details`, `get_clinvar_meta` |
| `gnomad_link/mcp/tools/coordinates.py` | `liftover_variant`, `get_region` |
| `gnomad_link/mcp/tools/specialty.py` | `get_structural_variant`, `get_mitochondrial_variant`, `get_transcript_details` |
| `gnomad_link/mcp/tools/search.py` | `search_genes`, `resolve_variant_id`, deprecated `search_variants` alias |
| `gnomad_link/services/frequency_service.py` | Adds 12 new service methods (one per data tool) |
| `gnomad_link/models/region_models.py` | New `Region`, `RegionGene`, `RegionClinVarVariant` |
| `gnomad_link/models/transcript_models.py` | New `Transcript`, `TranscriptExon` |
| `gnomad_link/models/variant_models.py` | Adds `VariantDetails`, `VariantSearchResult` |
| `gnomad_link/server_manager.py` | Strips `FastMCP.from_fastapi`, mounts hand-authored facade, deletes utility/route wiring |
| `gnomad_link/cli.py` | Adds `gnomad-link cache clear/stats` subcommands (REST replacement) |
| `tests/unit/mcp/test_mcp_facade_surface.py` | Tool-name regex, annotations, output schemas, instructions |
| `tests/unit/mcp/test_mcp_errors.py` | Error envelope shape and sanitization |
| `tests/unit/mcp/test_frequency_shaping.py` | Population filtering correctness |
| `tests/unit/mcp/test_large_response_shaping.py` | `get_region`, `get_gene_variants` limits |
| `tests/unit/mcp/test_mcp_client_smoke.py` | In-process FastMCP client |
| `tests/unit/mcp/test_mcp_capabilities.py` | Capabilities resource shape |
| Deleted | `gnomad_link/api/routes/{variant,gene,clinvar,liftover,structural_variant,mitochondrial,region,transcript,search}.py` |
| Deleted | `tests/integration/test_*_endpoints.py` (9 files; replaced by MCP smoke + service-layer tests) |

---

### Task 1: Lock Current Expectations With Failing Surface Tests

**Files:**
- Create: `tests/unit/mcp/__init__.py`
- Create: `tests/unit/mcp/test_mcp_facade_surface.py`
- Create: `tests/unit/mcp/conftest.py`

- [ ] **Step 1: Create the mcp test package marker**

Create empty `tests/unit/mcp/__init__.py`.

- [ ] **Step 2: Create a shared no-network service factory**

Create `tests/unit/mcp/conftest.py`:

```python
from __future__ import annotations

import pytest


@pytest.fixture
def fake_service_factory():
    def factory():
        raise AssertionError(
            "Surface tests must not invoke the gnomAD service; "
            "tests that need a stub service should override this fixture."
        )

    return factory
```

- [ ] **Step 3: Write the failing surface test**

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
    "resolve_variant_id",
    "search_variants",  # deprecated alias retained for one release
}

EXPECTED_DATA_TOOLS = EXPECTED_TOOLS - {"get_server_capabilities"}

EXPECTED_RESOURCE_URIS = {
    "gnomad://capabilities",
    "gnomad://usage",
}


@pytest.mark.asyncio
async def test_create_gnomad_mcp_exposes_expected_tool_names(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    tool_names = {tool.name for tool in await mcp.list_tools()}

    assert EXPECTED_TOOLS <= tool_names
    assert "clear_cache" not in tool_names
    assert "get_structural_variants" not in tool_names
    assert "get_variant_frequency_data" not in tool_names


@pytest.mark.asyncio
async def test_all_tool_names_match_anthropic_remote_mcp_regex(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    offenders = [
        tool.name
        for tool in await mcp.list_tools()
        if not ANTHROPIC_TOOL_NAME_RE.fullmatch(tool.name)
    ]

    assert offenders == []


@pytest.mark.asyncio
async def test_every_data_tool_has_read_only_open_world_annotations(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    tools_by_name = {tool.name: tool for tool in await mcp.list_tools()}

    for name in EXPECTED_DATA_TOOLS:
        ann = tools_by_name[name].annotations
        assert ann is not None, f"{name} missing annotations"
        assert ann.readOnlyHint is True, f"{name} not read-only"
        assert ann.destructiveHint is False, f"{name} marked destructive"
        assert ann.idempotentHint is True, f"{name} not idempotent"
        assert ann.openWorldHint is True, f"{name} should be open-world"


@pytest.mark.asyncio
async def test_capabilities_tool_is_closed_world(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    tools_by_name = {tool.name: tool for tool in await mcp.list_tools()}
    ann = tools_by_name["get_server_capabilities"].annotations

    assert ann is not None
    assert ann.openWorldHint is False


@pytest.mark.asyncio
async def test_every_data_tool_advertises_output_schema(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    tools_by_name = {tool.name: tool for tool in await mcp.list_tools()}

    for name in EXPECTED_DATA_TOOLS:
        schema = tools_by_name[name].outputSchema
        assert schema is not None, f"{name} missing outputSchema"
        assert isinstance(schema, dict)


@pytest.mark.asyncio
async def test_every_tool_description_leads_with_use_this_when(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    offenders = [
        tool.name
        for tool in await mcp.list_tools()
        if not (tool.description or "").lstrip().lower().startswith("use this when")
    ]
    assert offenders == [], f"tools missing LLM-routing description: {offenders}"


def test_server_instructions_include_workflows_and_safety(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    instructions = (
        create_gnomad_mcp(service_factory=fake_service_factory).instructions or ""
    )

    assert "Variant frequency" in instructions
    assert "get_server_capabilities" in instructions
    assert "gnomad://capabilities" in instructions
    assert "Research use only" in instructions
    assert len(instructions) < 1400


@pytest.mark.asyncio
async def test_capabilities_resources_are_registered(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    resource_uris = {str(res.uri) for res in await mcp.list_resources()}
    assert EXPECTED_RESOURCE_URIS <= resource_uris
```

- [ ] **Step 4: Run the focused tests and confirm they fail**

Run:

```bash
uv run pytest tests/unit/mcp/test_mcp_facade_surface.py -q
```

Expected: ImportError on `gnomad_link.mcp.facade` for every test.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/mcp/
git commit -m "test: lock expected mcp facade surface"
```

---

### Task 2: Add Annotation Constants, Error Envelope, And `run_mcp_tool`

**Files:**
- Create: `gnomad_link/mcp/__init__.py`
- Create: `gnomad_link/mcp/annotations.py`
- Create: `gnomad_link/mcp/errors.py`
- Create: `tests/unit/mcp/test_mcp_errors.py`

- [ ] **Step 1: Write failing error envelope tests**

Create `tests/unit/mcp/test_mcp_errors.py`:

```python
from __future__ import annotations

import json

import pytest


def test_mcp_tool_error_envelope_contains_required_fields() -> None:
    from gnomad_link.mcp.errors import McpErrorContext, mcp_tool_error

    err = mcp_tool_error(
        ValueError("invalid variant id 'abc'"),
        McpErrorContext(tool_name="get_variant_frequencies", variant_id="abc"),
    )
    payload = json.loads(str(err))

    assert payload["success"] is False
    assert payload["error_code"] == "validation_failed"
    assert payload["retryable"] is False
    assert "abc" not in payload["message"] or payload["message"].startswith("Invalid")
    assert payload["fallback_tool"] in {"get_server_capabilities", None}
    assert "_meta" in payload
    assert payload["_meta"]["unsafe_for_clinical_use"] is True


def test_data_not_found_maps_to_not_found_code() -> None:
    from gnomad_link.api import DataNotFoundError
    from gnomad_link.mcp.errors import McpErrorContext, mcp_tool_error

    err = mcp_tool_error(
        DataNotFoundError("variant 1-99999999-N-N not in gnomad_r4"),
        McpErrorContext(tool_name="get_variant_frequencies", variant_id="1-99999999-N-N"),
    )
    payload = json.loads(str(err))

    assert payload["error_code"] == "not_found"
    assert payload["retryable"] is False
    assert payload["recovery"]


def test_upstream_api_error_is_retryable() -> None:
    from gnomad_link.api import GnomadApiError
    from gnomad_link.mcp.errors import McpErrorContext, mcp_tool_error

    err = mcp_tool_error(
        GnomadApiError("upstream 503"),
        McpErrorContext(tool_name="get_variant_frequencies"),
    )
    payload = json.loads(str(err))

    assert payload["error_code"] == "upstream_unavailable"
    assert payload["retryable"] is True


@pytest.mark.asyncio
async def test_run_mcp_tool_returns_envelope_on_exception() -> None:
    from gnomad_link.mcp.errors import run_mcp_tool

    async def boom() -> None:
        raise RuntimeError("oh no a secret: SECRET")

    result = await run_mcp_tool("test_tool", boom)

    assert result["success"] is False
    assert result["error_code"] == "internal_error"
    assert "SECRET" not in result["message"]


@pytest.mark.asyncio
async def test_run_mcp_tool_passes_through_success_payload() -> None:
    from gnomad_link.mcp.errors import run_mcp_tool

    async def ok() -> dict[str, str]:
        return {"ok": "yes"}

    result = await run_mcp_tool("test_tool", ok)

    assert result == {"ok": "yes"}


def test_recent_error_ring_is_bounded() -> None:
    from gnomad_link.mcp.errors import RECENT_MCP_ERROR_LIMIT, get_recent_errors, record_mcp_error

    for i in range(RECENT_MCP_ERROR_LIMIT + 10):
        record_mcp_error(
            tool_name="get_variant_frequencies",
            error_code="internal_error",
            message=f"err {i}",
            raw_message=f"err {i}",
        )

    history = get_recent_errors()
    assert len(history) == RECENT_MCP_ERROR_LIMIT
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
uv run pytest tests/unit/mcp/test_mcp_errors.py -q
```

Expected: ImportError on `gnomad_link.mcp.errors`.

- [ ] **Step 3: Create the package marker**

Create `gnomad_link/mcp/__init__.py`:

```python
"""Hand-authored MCP facade for gnomAD Link."""

from gnomad_link.mcp.facade import create_gnomad_mcp

__all__ = ["create_gnomad_mcp"]
```

- [ ] **Step 4: Add annotation constants**

Create `gnomad_link/mcp/annotations.py`:

```python
"""Shared MCP tool annotations for gnomAD Link."""

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

- [ ] **Step 5: Implement the error envelope and `run_mcp_tool`**

Create `gnomad_link/mcp/errors.py`:

```python
"""Structured MCP error envelopes for gnomAD Link tools.

Patterned after pubtator_link/mcp/errors.py. The envelope shape is what LLMs
branch on; codes are deterministic per exception class so prompts can recover
without scraping free text.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from gnomad_link.api import DataNotFoundError, GnomadApiError

logger = logging.getLogger(__name__)

RECENT_MCP_ERROR_LIMIT = 50
_RECENT_ERRORS: deque[dict[str, Any]] = deque(maxlen=RECENT_MCP_ERROR_LIMIT)

_RESEARCH_USE_META = {"unsafe_for_clinical_use": True}


@dataclass
class McpErrorContext:
    """Per-call context passed to the error builder so envelopes can suggest fallbacks."""

    tool_name: str
    variant_id: str | None = None
    gene_id: str | None = None
    gene_symbol: str | None = None
    region: str | None = None
    dataset: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class McpToolError(Exception):
    """An exception whose `str(self)` is the JSON-serialised envelope."""

    def __init__(self, payload: dict[str, Any]):
        super().__init__(json.dumps(payload))
        self.payload = payload


def _safe_message(exc: BaseException) -> str:
    text = str(exc) or exc.__class__.__name__
    # gnomAD errors are user-input shaped; trim long tracebacks/identifiers.
    return text[:240]


def _classify(exc: BaseException) -> tuple[str, bool, str | None, dict[str, Any] | None]:
    """Return (error_code, retryable, fallback_tool, fallback_args)."""

    if isinstance(exc, DataNotFoundError):
        return "not_found", False, "search_genes", None
    if isinstance(exc, ValueError):
        return "validation_failed", False, "get_server_capabilities", None
    if isinstance(exc, GnomadApiError):
        return "upstream_unavailable", True, None, None
    if isinstance(exc, TimeoutError):
        return "upstream_unavailable", True, None, None
    return "internal_error", False, None, None


def _recovery_text(error_code: str, fallback_tool: str | None) -> str:
    if error_code == "not_found":
        return (
            "Variant or gene not present in the requested dataset. "
            "Try a different dataset (gnomad_r4 default; r3/r2_1 for older builds) "
            "or use search_genes / resolve_variant_id to verify the identifier."
        )
    if error_code == "validation_failed":
        return (
            "Inputs failed validation. Check the tool schema and call "
            "get_server_capabilities for accepted dataset and population codes."
        )
    if error_code == "upstream_unavailable":
        return "gnomAD upstream API failed. Safe to retry with exponential backoff."
    return f"Unexpected failure. Call {fallback_tool} for a safe entry point." if fallback_tool else (
        "Unexpected failure."
    )


def mcp_tool_error(exc: BaseException, context: McpErrorContext) -> McpToolError:
    error_code, retryable, fallback_tool, fallback_args = _classify(exc)
    payload = {
        "success": False,
        "error_code": error_code,
        "message": _safe_message(exc),
        "retryable": retryable,
        "fallback_tool": fallback_tool,
        "fallback_args": fallback_args,
        "recovery": _recovery_text(error_code, fallback_tool),
        "_meta": {
            "tool": context.tool_name,
            "next_commands": [
                "get_server_capabilities",
                "gnomad://capabilities",
            ],
            **_RESEARCH_USE_META,
        },
    }
    return McpToolError(payload)


def record_mcp_error(
    *, tool_name: str, error_code: str, message: str, raw_message: str
) -> None:
    _RECENT_ERRORS.append(
        {
            "tool_name": tool_name,
            "error_code": error_code,
            "message": message,
            "raw_message": raw_message[:500],
        }
    )


def get_recent_errors() -> list[dict[str, Any]]:
    return list(_RECENT_ERRORS)


def clear_recent_errors() -> None:
    _RECENT_ERRORS.clear()


async def run_mcp_tool(
    tool_name: str,
    call: Callable[[], Awaitable[Any]],
    *,
    context: McpErrorContext | None = None,
) -> Any:
    """Execute an MCP tool body, converting any exception to an envelope dict.

    Returning the envelope (rather than raising) is what pubtator-link does so
    that the LLM sees a structured failure instead of an `isError: true` MCP
    response with an opaque message.
    """

    ctx = context or McpErrorContext(tool_name=tool_name)
    try:
        return await call()
    except McpToolError as exc:
        record_mcp_error(
            tool_name=tool_name,
            error_code=exc.payload.get("error_code", "internal_error"),
            message=exc.payload.get("message", ""),
            raw_message=str(exc),
        )
        return exc.payload
    except Exception as exc:  # noqa: BLE001 - boundary
        wrapped = mcp_tool_error(exc, ctx)
        logger.warning(
            "mcp_tool_error tool=%s code=%s exc=%s",
            tool_name,
            wrapped.payload["error_code"],
            exc.__class__.__name__,
        )
        record_mcp_error(
            tool_name=tool_name,
            error_code=wrapped.payload["error_code"],
            message=wrapped.payload["message"],
            raw_message=str(exc),
        )
        return wrapped.payload
```

- [ ] **Step 6: Run the error tests to verify they pass**

```bash
uv run pytest tests/unit/mcp/test_mcp_errors.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add gnomad_link/mcp/__init__.py gnomad_link/mcp/annotations.py gnomad_link/mcp/errors.py tests/unit/mcp/test_mcp_errors.py
git commit -m "feat(mcp): add annotation constants and structured error envelope"
```

---

### Task 3: Add Capabilities Resources And Facade Skeleton

**Files:**
- Create: `gnomad_link/mcp/resources.py`
- Create: `gnomad_link/mcp/facade.py`
- Create: `gnomad_link/mcp/tools/__init__.py`
- Create: `gnomad_link/mcp/tools/metadata.py`
- Create: `tests/unit/mcp/test_mcp_capabilities.py`

- [ ] **Step 1: Write failing capability tests**

Create `tests/unit/mcp/test_mcp_capabilities.py`:

```python
from __future__ import annotations

import pytest


def test_capabilities_payload_shape() -> None:
    from gnomad_link.mcp.resources import get_capabilities_resource

    payload = get_capabilities_resource()

    assert payload["server"] == "gnomad-link"
    assert payload["research_use_only"] is True
    assert "gnomad_r4" in payload["datasets"]
    assert payload["datasets"]["gnomad_r4"]["default"] is True
    assert "afr" in payload["population_codes"]
    assert "_XX" in payload["population_suffixes"]
    assert "variant_id -> get_variant_frequencies" in payload["recommended_workflows"]
    assert "resolve_variant_id" in payload["tools"]
    assert "get_variant_frequencies" in payload["tools"]


def test_capabilities_payload_includes_version_and_protocol() -> None:
    from gnomad_link.mcp.resources import get_capabilities_resource

    payload = get_capabilities_resource()

    assert "server_version" in payload
    assert "mcp_protocol_version" in payload


@pytest.mark.asyncio
async def test_get_server_capabilities_tool_returns_capabilities(fake_service_factory) -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    result = await mcp.call_tool("get_server_capabilities", {})

    payload = result.structured_content or {}
    assert payload["server"] == "gnomad-link"
    assert isinstance(payload["tools"], list)
```

- [ ] **Step 2: Run the capability tests to confirm failure**

```bash
uv run pytest tests/unit/mcp/test_mcp_capabilities.py -q
```

Expected: ImportError on `gnomad_link.mcp.resources`.

- [ ] **Step 3: Implement the capabilities resource**

Create `gnomad_link/mcp/resources.py`:

```python
"""Capabilities and usage payloads for the gnomAD Link MCP server."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

RESEARCH_USE_NOTICE = "Research use only; not for clinical decision support."

MCP_PROTOCOL_VERSION = "2025-06-18"


def _server_version() -> str:
    try:
        return version("gnomad-link")
    except PackageNotFoundError:
        return "unknown"


def get_capabilities_resource() -> dict[str, Any]:
    return {
        "server": "gnomad-link",
        "server_version": _server_version(),
        "mcp_protocol_version": MCP_PROTOCOL_VERSION,
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
            "rsID or loose text -> resolve_variant_id -> get_variant_frequencies",
            "gene symbol -> search_genes -> get_gene_details",
            "clinical annotation -> get_clinvar_variant_details + get_variant_frequencies",
            "build conversion -> liftover_variant",
            "region scan -> get_region (cap span at 100kb; use include_clinvar/include_genes)",
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
            "resolve_variant_id",
            "search_variants",
        ],
        "deprecated_tools": {
            "search_variants": "Use resolve_variant_id; this alias is retained for one release.",
        },
        "limitations": [
            "Default local CI avoids live gnomAD calls.",
            "get_region capped at 100kb span; get_gene_variants capped at 500 rows.",
            "Population truncation: subcohort and sex-split rows are omitted by default.",
            RESEARCH_USE_NOTICE,
        ],
    }


def get_usage_resource() -> str:
    return (
        "# gnomAD Link MCP Usage\n\n"
        "Use CHROM-POS-REF-ALT variant IDs (GRCh38 by default) for SNV/indel frequencies. "
        "Use M-POS-REF-ALT for mitochondrial variants. Compact responses are the default; "
        "request `response_mode=\"full\"` for debugging and `include_subcohorts=True` to "
        "expand population subgroup rows.\n\n"
        f"{RESEARCH_USE_NOTICE}"
    )
```

- [ ] **Step 4: Implement the metadata tool module**

Create `gnomad_link/mcp/tools/__init__.py`:

```python
"""Tool registration entry points for the gnomAD Link MCP facade."""

from __future__ import annotations

from collections.abc import Callable

from fastmcp import FastMCP

from gnomad_link.services import FrequencyService

from gnomad_link.mcp.tools.metadata import register_metadata_tools


def register_gnomad_tools(
    mcp: FastMCP,
    *,
    service_factory: Callable[[], FrequencyService],
) -> None:
    register_metadata_tools(mcp)
    # Data tool registrations are added in later tasks.
```

Create `gnomad_link/mcp/tools/metadata.py`:

```python
"""Capabilities tool plus resource handlers."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from gnomad_link.mcp.annotations import READ_ONLY_CLOSED_WORLD
from gnomad_link.mcp.errors import run_mcp_tool
from gnomad_link.mcp.resources import get_capabilities_resource, get_usage_resource


def register_metadata_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        name="get_server_capabilities",
        title="Get gnomAD Link Capabilities",
        annotations=READ_ONLY_CLOSED_WORLD,
    )
    async def get_server_capabilities() -> dict[str, Any]:
        """Use this when a client needs supported tools, datasets, population codes, recommended workflows, or current limitations."""

        return await run_mcp_tool(
            "get_server_capabilities",
            lambda: _coro_capabilities(),
        )

    @mcp.resource("gnomad://capabilities")
    def capabilities_resource() -> dict[str, Any]:
        return get_capabilities_resource()

    @mcp.resource("gnomad://usage")
    def usage_resource() -> str:
        return get_usage_resource()


async def _coro_capabilities() -> dict[str, Any]:
    return get_capabilities_resource()
```

- [ ] **Step 5: Implement the facade skeleton**

Create `gnomad_link/mcp/facade.py`:

```python
"""Hand-authored FastMCP facade for gnomAD Link."""

from __future__ import annotations

from collections.abc import Callable

from fastmcp import FastMCP

from gnomad_link.mcp.resources import RESEARCH_USE_NOTICE
from gnomad_link.mcp.tools import register_gnomad_tools
from gnomad_link.services import FrequencyService

_INSTRUCTIONS = (
    "gnomAD Link grounds population-genetics work in gnomAD datasets.\n"
    "- Variant frequency: get_variant_frequencies for CHROM-POS-REF-ALT; "
    "resolve_variant_id first for rsIDs or loose text.\n"
    "- Clinical annotation: pair get_clinvar_variant_details with "
    "get_variant_frequencies.\n"
    "- Gene constraint: search_genes then get_gene_details.\n"
    "- Coordinates: liftover_variant converts between GRCh37 and GRCh38.\n"
    "- Special variants: get_structural_variant for SVs; "
    "get_mitochondrial_variant for M-POS-REF-ALT.\n"
    "- Region scans: get_region with include_clinvar/include_genes; "
    "cap span at 100kb.\n"
    "- Datasets: gnomad_r2_1 is GRCh37; gnomad_r3 and gnomad_r4 are GRCh38; "
    "gnomad_r4 is default.\n"
    "- Compact defaults trim subcohort and zero-AC populations; pass "
    "include_subcohorts=True or response_mode='full' for raw payloads.\n"
    "- Discovery: call get_server_capabilities or read gnomad://capabilities. "
    f"{RESEARCH_USE_NOTICE}"
)


def create_gnomad_mcp(
    *,
    service_factory: Callable[[], FrequencyService],
) -> FastMCP:
    """Build the gnomAD Link MCP server.

    `service_factory` is a lazy callable so HTTP mode can defer to
    `app.state.frequency_service` and stdio mode can hold a directly
    constructed instance.
    """

    mcp = FastMCP(
        name="gnomad-link",
        instructions=_INSTRUCTIONS,
        mask_error_details=True,
    )
    register_gnomad_tools(mcp, service_factory=service_factory)
    return mcp
```

- [ ] **Step 6: Run the capability and surface tests**

```bash
uv run pytest tests/unit/mcp/test_mcp_capabilities.py tests/unit/mcp/test_mcp_facade_surface.py::test_server_instructions_include_workflows_and_safety tests/unit/mcp/test_mcp_facade_surface.py::test_capabilities_resources_are_registered -q
```

Expected: PASS. Other surface tests still fail (no data tools yet).

- [ ] **Step 7: Commit**

```bash
git add gnomad_link/mcp/resources.py gnomad_link/mcp/facade.py gnomad_link/mcp/tools/ tests/unit/mcp/test_mcp_capabilities.py
git commit -m "feat(mcp): add facade skeleton with capabilities tool and resources"
```

---

### Task 4: Add Missing Service Methods

**Files:**
- Modify: `gnomad_link/services/frequency_service.py`
- Modify: `gnomad_link/services/__init__.py` (only if symbols are re-exported)
- Test: `tests/unit/test_frequency_service_methods.py`

The current `FrequencyService` exposes only `get_variant_frequencies`. The other 12 tools currently reach into `service.client.*` directly. The facade should call service methods so caching, instrumentation, and tests have a single seam.

- [ ] **Step 1: Write failing tests for the new service methods**

Create `tests/unit/test_frequency_service_methods.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from gnomad_link.services.frequency_service import FrequencyService


@pytest.fixture
def service_with_stub_client():
    client = AsyncMock()
    return FrequencyService(client=client), client


@pytest.mark.asyncio
async def test_get_variant_delegates_to_client(service_with_stub_client) -> None:
    service, client = service_with_stub_client
    client.get_variant.return_value = {"variant_id": "1-1-A-T"}

    result = await service.get_variant("1-1-A-T", "gnomad_r4")

    client.get_variant.assert_awaited_once_with("1-1-A-T", "gnomad_r4")
    assert result["variant_id"] == "1-1-A-T"


@pytest.mark.asyncio
async def test_get_gene_delegates_to_client(service_with_stub_client) -> None:
    service, client = service_with_stub_client
    client.get_gene.return_value = {"symbol": "PCSK9"}

    result = await service.get_gene(gene_symbol="PCSK9", reference_genome="GRCh38")

    client.get_gene.assert_awaited_once_with(None, "PCSK9", "GRCh38", None)
    assert result["symbol"] == "PCSK9"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "service_method,client_method,args",
    [
        ("get_gene_variants", "get_gene_variants", ("ENSG1", "gnomad_r4")),
        ("get_clinvar_variant", "get_clinvar_variant", ("1-1-A-T", "GRCh38")),
        ("get_clinvar_meta", "get_meta", ()),
        ("get_structural_variant", "get_structural_variant", ("SV_1", "gnomad_sv_r4")),
        ("get_mitochondrial_variant", "get_mitochondrial_variant", ("M-1-A-T", "gnomad_r4")),
        ("get_region", "get_region", ("1", 1, 100, "gnomad_r4")),
        ("get_transcript", "get_transcript", ("ENST1", "GRCh38")),
        ("search_variants", "search_variants", ("PCSK9", "gnomad_r4")),
        ("liftover_variant", "get_liftover", ("1-1-A-T", "GRCh38")),
    ],
)
async def test_service_methods_delegate(service_with_stub_client, service_method, client_method, args) -> None:
    service, client = service_with_stub_client
    getattr(client, client_method).return_value = {"ok": True}

    result = await getattr(service, service_method)(*args)

    getattr(client, client_method).assert_awaited_once_with(*args)
    assert result == {"ok": True}
```

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/unit/test_frequency_service_methods.py -q
```

Expected: AttributeError on the new methods.

- [ ] **Step 3: Add the service methods**

Append to `gnomad_link/services/frequency_service.py` (keep existing imports, dataclass, and `get_variant_frequencies`):

```python
    async def get_variant(self, variant_id: str, dataset: str = "gnomad_r4") -> dict[str, Any]:
        return await self.client.get_variant(variant_id, dataset)

    async def get_gene(
        self,
        gene_id: str | None = None,
        gene_symbol: str | None = None,
        reference_genome: str | None = None,
        dataset: str | None = None,
    ) -> dict[str, Any]:
        return await self.client.get_gene(gene_id, gene_symbol, reference_genome, dataset)

    async def get_gene_variants(
        self, gene_id: str, dataset: str = "gnomad_r4"
    ) -> list[dict[str, Any]]:
        return await self.client.get_gene_variants(gene_id, dataset)

    async def get_clinvar_variant(
        self, variant_id: str, reference_genome: str = "GRCh38"
    ) -> dict[str, Any]:
        return await self.client.get_clinvar_variant(variant_id, reference_genome)

    async def get_clinvar_meta(self) -> dict[str, Any]:
        return await self.client.get_meta()

    async def get_structural_variant(
        self, variant_id: str, dataset: str = "gnomad_sv_r4"
    ) -> dict[str, Any]:
        return await self.client.get_structural_variant(variant_id, dataset)

    async def get_mitochondrial_variant(
        self, variant_id: str, dataset: str = "gnomad_r4"
    ) -> dict[str, Any]:
        return await self.client.get_mitochondrial_variant(variant_id, dataset)

    async def get_region(
        self, chrom: str, start: int, stop: int, dataset: str = "gnomad_r4"
    ) -> dict[str, Any]:
        return await self.client.get_region(chrom, start, stop, dataset)

    async def get_transcript(
        self, transcript_id: str, reference_genome: str = "GRCh38"
    ) -> dict[str, Any]:
        return await self.client.get_transcript(transcript_id, reference_genome)

    async def search_variants(
        self, query: str, dataset: str = "gnomad_r4"
    ) -> list[dict[str, Any]]:
        return await self.client.search_variants(query, dataset)

    async def liftover_variant(
        self, source_variant_id: str, reference_genome: str = "GRCh38"
    ) -> list[dict[str, Any]]:
        return await self.client.get_liftover(source_variant_id, reference_genome)
```

If the client signature for any method differs from what the tests assume (verify by reading `gnomad_link/api/client.py`), align the wrapper signature to the real client — do **not** edit the client.

- [ ] **Step 4: Run the service method tests**

```bash
uv run pytest tests/unit/test_frequency_service_methods.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add gnomad_link/services/frequency_service.py tests/unit/test_frequency_service_methods.py
git commit -m "feat(services): add service-layer wrappers for all gnomad data tools"
```

---

### Task 5: Add New Pydantic Models For Untyped Tools

**Files:**
- Create: `gnomad_link/models/region_models.py`
- Create: `gnomad_link/models/transcript_models.py`
- Modify: `gnomad_link/models/variant_models.py`
- Modify: `gnomad_link/models/__init__.py`
- Test: `tests/unit/test_new_models.py`

Tools currently returning `dict[str, Any]` need response models so MCP `outputSchema` can be advertised.

- [ ] **Step 1: Write a failing roundtrip test for each new model**

Create `tests/unit/test_new_models.py`:

```python
from __future__ import annotations

import pytest


def test_region_model_roundtrip() -> None:
    from gnomad_link.models.region_models import Region

    payload = {
        "chrom": "17",
        "start": 7674232,
        "stop": 7674252,
        "reference_genome": "GRCh38",
        "genes": [{"gene_id": "ENSG00000141510", "symbol": "TP53", "start": 7661779, "stop": 7687538}],
        "clinvar_variants": [
            {
                "variant_id": "17-7674232-C-G",
                "clinical_significance": "Pathogenic",
                "gold_stars": 2,
                "major_consequence": "missense_variant",
                "pos": 7674232,
                "review_status": "criteria provided, multiple submitters, no conflicts",
            }
        ],
    }
    region = Region.model_validate(payload)
    assert region.chrom == "17"
    assert region.genes[0].symbol == "TP53"


def test_transcript_model_roundtrip() -> None:
    from gnomad_link.models.transcript_models import Transcript

    payload = {
        "transcript_id": "ENST00000302118",
        "gene_id": "ENSG00000169174",
        "gene_symbol": "PCSK9",
        "chrom": "1",
        "start": 55039549,
        "stop": 55064852,
        "strand": "+",
        "reference_genome": "GRCh38",
        "exons": [{"feature_type": "CDS", "start": 55039549, "stop": 55039750}],
    }
    transcript = Transcript.model_validate(payload)
    assert transcript.gene_symbol == "PCSK9"
    assert transcript.exons[0].feature_type == "CDS"


def test_variant_details_accepts_unknown_fields() -> None:
    """gnomAD adds fields over time; variant details must not reject upstream growth."""

    from gnomad_link.models.variant_models import VariantDetails

    payload = {
        "variant_id": "1-55051215-G-GA",
        "reference_genome": "GRCh38",
        "pos": 55051215,
        "ref": "G",
        "alt": "GA",
        "rsids": ["rs11591147"],
        "future_field_we_dont_know": {"surprise": True},
    }
    details = VariantDetails.model_validate(payload)
    assert details.variant_id == "1-55051215-G-GA"


def test_variant_search_result_model() -> None:
    from gnomad_link.models.variant_models import VariantSearchResult

    result = VariantSearchResult.model_validate({"variant_id": "1-55051215-G-GA"})
    assert result.variant_id == "1-55051215-G-GA"
```

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/unit/test_new_models.py -q
```

Expected: ImportError on the new modules.

- [ ] **Step 3: Implement `region_models.py`**

Create `gnomad_link/models/region_models.py`:

```python
"""Pydantic models for genomic region queries."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RegionGene(BaseModel):
    gene_id: str
    symbol: str
    start: int
    stop: int


class RegionClinVarVariant(BaseModel):
    variant_id: str
    clinical_significance: str | None = None
    gold_stars: int | None = None
    major_consequence: str | None = None
    pos: int
    review_status: str | None = None


class Region(BaseModel):
    chrom: str
    start: int
    stop: int
    reference_genome: str
    genes: list[RegionGene] = Field(default_factory=list)
    clinvar_variants: list[RegionClinVarVariant] = Field(default_factory=list)
    variants: list[dict] | None = None  # SNV/indel array; opaque until shaping covers it
    truncated: dict | None = Field(default=None, description="Set when filters or limits dropped rows")

    model_config = ConfigDict(extra="allow")
```

- [ ] **Step 4: Implement `transcript_models.py`**

Create `gnomad_link/models/transcript_models.py`:

```python
"""Pydantic models for transcript queries."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TranscriptExon(BaseModel):
    feature_type: str
    start: int
    stop: int


class Transcript(BaseModel):
    transcript_id: str
    gene_id: str | None = None
    gene_symbol: str | None = None
    chrom: str
    start: int
    stop: int
    strand: str | None = None
    reference_genome: str
    exons: list[TranscriptExon] = Field(default_factory=list)
    gtex_tissue_expression: list[dict] | None = None

    model_config = ConfigDict(extra="allow")
```

- [ ] **Step 5: Extend `variant_models.py`**

Append to `gnomad_link/models/variant_models.py`:

```python
class VariantSearchResult(BaseModel):
    """Minimal result from resolve_variant_id / search_variants — IDs only."""

    variant_id: str = Field(..., description="gnomAD variant ID (CHROM-POS-REF-ALT)")
    rsid: str | None = None
    dataset: str | None = None


class VariantDetails(BaseModel):
    """Compact variant detail payload returned by get_variant_details in compact mode."""

    variant_id: str
    reference_genome: str | None = None
    pos: int | None = None
    ref: str | None = None
    alt: str | None = None
    rsids: list[str] = Field(default_factory=list)
    major_consequence: str | None = None
    transcript_consequences: list[dict] | None = None
    in_silico_predictors: dict | None = None
    clinvar: dict | None = None
    exome: dict | None = None
    genome: dict | None = None

    model_config = ConfigDict(extra="allow")
```

(Add `from pydantic import ConfigDict` to the imports if not already present.)

- [ ] **Step 6: Re-export from package init**

Edit `gnomad_link/models/__init__.py` to add the new symbols:

```python
from gnomad_link.models.region_models import Region, RegionGene, RegionClinVarVariant
from gnomad_link.models.transcript_models import Transcript, TranscriptExon
from gnomad_link.models.variant_models import VariantDetails, VariantSearchResult
```

(Preserve every existing re-export; only add to the list.)

- [ ] **Step 7: Run the new-model tests**

```bash
uv run pytest tests/unit/test_new_models.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add gnomad_link/models/ tests/unit/test_new_models.py
git commit -m "feat(models): add Region, Transcript, VariantDetails, VariantSearchResult"
```

---

### Task 6: Add Response Shaping Helpers

**Files:**
- Create: `gnomad_link/mcp/shaping.py`
- Test: `tests/unit/mcp/test_frequency_shaping.py`

These helpers are pure functions over service responses. They live outside the tool modules so they can be unit-tested without spinning up FastMCP.

- [ ] **Step 1: Write failing frequency-shaping tests**

Create `tests/unit/mcp/test_frequency_shaping.py`:

```python
from __future__ import annotations

import pytest

from gnomad_link.models import VariantDataSource, VariantFrequencyResponse
from gnomad_link.models.variant_models import PopulationFrequency


def _make_response() -> VariantFrequencyResponse:
    exome = VariantDataSource(
        ac=200,
        an=300_000,
        homozygote_count=2,
        populations=[
            PopulationFrequency.model_validate({"id": "afr", "ac": 143, "an": 8_000, "homozygote_count": 2}),
            PopulationFrequency.model_validate({"id": "nfe", "ac": 7, "an": 150_000, "homozygote_count": 0}),
            PopulationFrequency.model_validate({"id": "non_topmed_afr", "ac": 80, "an": 5_000, "homozygote_count": 1}),
            PopulationFrequency.model_validate({"id": "afr_XX", "ac": 70, "an": 4_000, "homozygote_count": 1}),
            PopulationFrequency.model_validate({"id": "asj", "ac": 0, "an": 1_000, "homozygote_count": 0}),
        ],
    )
    return VariantFrequencyResponse(variant_id="1-1-A-T", dataset="gnomad_r4", exome=exome, genome=None)


def test_default_shape_drops_zero_subcohort_and_sex_split() -> None:
    from gnomad_link.mcp.shaping import shape_variant_frequencies

    payload = shape_variant_frequencies(
        _make_response(),
        populations=None,
        include_subcohorts=False,
        include_sex_split=False,
        exclude_zero_populations=True,
    )

    pops = {p["id"] for p in payload["exome"]["populations"]}
    assert pops == {"afr", "nfe"}
    assert payload["exome"]["populations"][0]["af"] == pytest.approx(143 / 8_000)


def test_truncated_block_explains_what_was_dropped() -> None:
    from gnomad_link.mcp.shaping import shape_variant_frequencies

    payload = shape_variant_frequencies(
        _make_response(),
        populations=None,
        include_subcohorts=False,
        include_sex_split=False,
        exclude_zero_populations=True,
    )

    trunc = payload["exome"]["truncated"]
    assert trunc["kind"] == "populations"
    assert trunc["dropped"]["subcohorts"] == 1
    assert trunc["dropped"]["sex_split"] == 1
    assert trunc["dropped"]["zero_ac"] == 1
    assert "include_subcohorts" in trunc["to_disable"]


def test_populations_filter_restricts_rows() -> None:
    from gnomad_link.mcp.shaping import shape_variant_frequencies

    payload = shape_variant_frequencies(
        _make_response(),
        populations=["afr"],
        include_subcohorts=False,
        include_sex_split=False,
        exclude_zero_populations=True,
    )

    assert [p["id"] for p in payload["exome"]["populations"]] == ["afr"]


def test_include_subcohorts_keeps_prefixed_rows() -> None:
    from gnomad_link.mcp.shaping import shape_variant_frequencies

    payload = shape_variant_frequencies(
        _make_response(),
        populations=None,
        include_subcohorts=True,
        include_sex_split=False,
        exclude_zero_populations=True,
    )

    pops = {p["id"] for p in payload["exome"]["populations"]}
    assert "non_topmed_afr" in pops
```

- [ ] **Step 2: Run and confirm failure**

```bash
uv run pytest tests/unit/mcp/test_frequency_shaping.py -q
```

Expected: ImportError on `gnomad_link.mcp.shaping`.

- [ ] **Step 3: Implement frequency shaping**

Create `gnomad_link/mcp/shaping.py`:

```python
"""Pure helpers that project gnomAD service responses into MCP-compact shapes."""

from __future__ import annotations

from typing import Any, Iterable

from gnomad_link.models import VariantFrequencyResponse

BASE_POPULATION_CODES = {
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
}

SUBCOHORT_PREFIXES = ("non_topmed_", "non_ukb_", "non_v2_", "1kg_", "hgdp_", "controls_")


def _is_subcohort(pop_id: str) -> bool:
    return pop_id.startswith(SUBCOHORT_PREFIXES)


def _is_sex_split(pop_id: str) -> bool:
    return pop_id.endswith(("_XX", "_XY"))


def _filter_populations(
    populations: list[Any],
    *,
    select: list[str] | None,
    include_subcohorts: bool,
    include_sex_split: bool,
    exclude_zero: bool,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    dropped = {"zero_ac": 0, "subcohorts": 0, "sex_split": 0, "not_selected": 0}
    kept: list[dict[str, Any]] = []
    for pop in populations:
        pop_id = getattr(pop, "name", None) or pop.get("id") or pop.get("name")
        ac = getattr(pop, "allele_count", None) or pop.get("ac", 0)
        an = getattr(pop, "allele_number", None) or pop.get("an", 0)
        hom = getattr(pop, "homozygote_count", None)
        if hom is None:
            hom = pop.get("homozygote_count", 0)
        if select is not None and pop_id not in select:
            dropped["not_selected"] += 1
            continue
        if not include_subcohorts and _is_subcohort(pop_id):
            dropped["subcohorts"] += 1
            continue
        if not include_sex_split and _is_sex_split(pop_id):
            dropped["sex_split"] += 1
            continue
        if exclude_zero and ac == 0:
            dropped["zero_ac"] += 1
            continue
        af = (ac / an) if an else None
        kept.append({"id": pop_id, "ac": ac, "an": an, "af": af, "homozygote_count": hom})
    return kept, dropped


def _shape_source(
    source: Any,
    *,
    select: list[str] | None,
    include_subcohorts: bool,
    include_sex_split: bool,
    exclude_zero: bool,
) -> dict[str, Any] | None:
    if source is None:
        return None
    ac = getattr(source, "ac", 0)
    an = getattr(source, "an", 0)
    populations, dropped = _filter_populations(
        getattr(source, "populations", []),
        select=select,
        include_subcohorts=include_subcohorts,
        include_sex_split=include_sex_split,
        exclude_zero=exclude_zero,
    )
    out: dict[str, Any] = {
        "ac": ac,
        "an": an,
        "af": (ac / an) if an else None,
        "homozygote_count": getattr(source, "homozygote_count", 0),
        "hemizygote_count": getattr(source, "hemizygote_count", None),
        "populations": populations,
    }
    total_dropped = sum(dropped.values())
    if total_dropped:
        out["truncated"] = {
            "kind": "populations",
            "dropped": dropped,
            "filter": {
                "include_subcohorts": include_subcohorts,
                "include_sex_split": include_sex_split,
                "exclude_zero_populations": exclude_zero,
                "populations": select,
            },
            "to_disable": (
                "set include_subcohorts=True and include_sex_split=True and "
                "exclude_zero_populations=False for the full upstream payload"
            ),
        }
    return out


def shape_variant_frequencies(
    response: VariantFrequencyResponse | dict[str, Any],
    *,
    populations: list[str] | None,
    include_subcohorts: bool,
    include_sex_split: bool,
    exclude_zero_populations: bool,
) -> dict[str, Any]:
    if isinstance(response, dict):
        response = VariantFrequencyResponse.model_validate(response)
    return {
        "variant_id": response.variant_id,
        "dataset": response.dataset,
        "exome": _shape_source(
            response.exome,
            select=populations,
            include_subcohorts=include_subcohorts,
            include_sex_split=include_sex_split,
            exclude_zero=exclude_zero_populations,
        ),
        "genome": _shape_source(
            response.genome,
            select=populations,
            include_subcohorts=include_subcohorts,
            include_sex_split=include_sex_split,
            exclude_zero=exclude_zero_populations,
        ),
    }


def shape_gene_variants(
    raw: list[dict[str, Any]],
    *,
    limit: int,
    consequence: str | None,
    max_af: float | None,
    min_ac: int | None,
) -> dict[str, Any]:
    """Filter and cap a gene-variants list. Always returns a `truncated` block when the cap fires."""

    if limit <= 0 or limit > 500:
        raise ValueError("limit must be in [1, 500]")
    filtered: list[dict[str, Any]] = []
    total_seen = 0
    dropped = {"by_consequence": 0, "by_max_af": 0, "by_min_ac": 0}
    for v in raw:
        total_seen += 1
        if consequence and v.get("consequence") != consequence and v.get("major_consequence") != consequence:
            dropped["by_consequence"] += 1
            continue
        if max_af is not None and (v.get("af") or 0.0) > max_af:
            dropped["by_max_af"] += 1
            continue
        if min_ac is not None and (v.get("ac") or 0) < min_ac:
            dropped["by_min_ac"] += 1
            continue
        filtered.append(v)
        if len(filtered) >= limit:
            break
    payload = {"variants": filtered, "returned": len(filtered), "total_seen": total_seen}
    if total_seen > len(filtered):
        payload["truncated"] = {
            "kind": "gene_variants",
            "dropped": dropped,
            "filter": {
                "limit": limit,
                "consequence": consequence,
                "max_af": max_af,
                "min_ac": min_ac,
            },
            "to_disable": "raise limit (max 500) or relax max_af/min_ac/consequence filters",
        }
    return payload


def shape_variant_details_compact(raw: dict[str, Any]) -> dict[str, Any]:
    """Project the gnomAD variant payload to the compact subset advertised in VariantDetails."""

    if not isinstance(raw, dict):
        return raw
    keep = {
        "variant_id",
        "reference_genome",
        "pos",
        "ref",
        "alt",
        "rsids",
        "major_consequence",
        "transcript_consequences",
        "in_silico_predictors",
        "clinvar",
        "exome",
        "genome",
    }
    return {k: v for k, v in raw.items() if k in keep}


def cap_region_span(chrom: str, start: int, stop: int, *, max_bp: int = 100_000) -> tuple[int, int, bool]:
    """Clamp a region request to `max_bp` and report whether truncation occurred."""

    span = stop - start
    if span <= max_bp:
        return start, stop, False
    return start, start + max_bp, True
```

- [ ] **Step 4: Run shaping tests**

```bash
uv run pytest tests/unit/mcp/test_frequency_shaping.py -q
```

Expected: PASS.

- [ ] **Step 5: Add the gene-variant and region cap tests**

Append to `tests/unit/mcp/test_large_response_shaping.py` (create the file):

```python
from __future__ import annotations

import pytest

from gnomad_link.mcp.shaping import cap_region_span, shape_gene_variants


def _gen_variants(n: int) -> list[dict]:
    return [
        {"variant_id": f"1-{i}-A-T", "af": (i % 10) / 10000, "ac": i, "major_consequence": "missense_variant"}
        for i in range(1, n + 1)
    ]


def test_gene_variants_limit_truncates() -> None:
    payload = shape_gene_variants(_gen_variants(250), limit=50, consequence=None, max_af=None, min_ac=None)
    assert payload["returned"] == 50
    assert payload["truncated"]["kind"] == "gene_variants"


def test_gene_variants_max_af_filter() -> None:
    payload = shape_gene_variants(
        _gen_variants(50), limit=100, consequence=None, max_af=0.0001, min_ac=None
    )
    assert all(v["af"] <= 0.0001 for v in payload["variants"])


def test_gene_variants_invalid_limit() -> None:
    with pytest.raises(ValueError):
        shape_gene_variants([], limit=0, consequence=None, max_af=None, min_ac=None)
    with pytest.raises(ValueError):
        shape_gene_variants([], limit=600, consequence=None, max_af=None, min_ac=None)


def test_cap_region_span_no_change_when_in_bounds() -> None:
    start, stop, capped = cap_region_span("1", 100, 1000)
    assert (start, stop, capped) == (100, 1000, False)


def test_cap_region_span_clamps() -> None:
    start, stop, capped = cap_region_span("1", 100, 1_000_000)
    assert capped is True
    assert stop - start == 100_000
```

- [ ] **Step 6: Run the large-response tests**

```bash
uv run pytest tests/unit/mcp/test_large_response_shaping.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add gnomad_link/mcp/shaping.py tests/unit/mcp/test_frequency_shaping.py tests/unit/mcp/test_large_response_shaping.py
git commit -m "feat(mcp): add response shaping helpers with explicit truncation metadata"
```

---

### Task 7: Register Data Tools (Variants + Genes)

**Files:**
- Create: `gnomad_link/mcp/tools/variants.py`
- Create: `gnomad_link/mcp/tools/genes.py`
- Modify: `gnomad_link/mcp/tools/__init__.py`

- [ ] **Step 1: Implement `variants.py`**

Create `gnomad_link/mcp/tools/variants.py`:

```python
"""Variant tools: get_variant_frequencies, get_variant_details."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool
from gnomad_link.mcp.shaping import (
    shape_variant_details_compact,
    shape_variant_frequencies,
)
from gnomad_link.models import VariantDetails
from gnomad_link.services import FrequencyService

_FREQ_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "variant_id": {"type": "string"},
        "dataset": {"type": "string"},
        "exome": {"type": ["object", "null"]},
        "genome": {"type": ["object", "null"]},
    },
    "required": ["variant_id", "dataset"],
    "additionalProperties": True,
}


def register_variant_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="get_variant_frequencies",
        title="Get Variant Frequencies",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=_FREQ_OUTPUT_SCHEMA,
    )
    async def get_variant_frequencies(
        variant_id: Annotated[
            str,
            Field(
                description="CHROM-POS-REF-ALT (e.g. 1-55051215-G-GA). Use M-POS-REF-ALT only with get_mitochondrial_variant.",
                min_length=5,
                max_length=200,
                pattern=r"^[^'\"]+$",
            ),
        ],
        dataset: Annotated[
            Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"],
            Field(description="Dataset. gnomad_r4 default (GRCh38)."),
        ] = "gnomad_r4",
        populations: Annotated[
            list[str] | None,
            Field(description="Restrict to these population codes (e.g. ['afr','nfe']). None returns all kept rows."),
        ] = None,
        include_subcohorts: Annotated[
            bool,
            Field(description="Include non_topmed_*, non_ukb_*, 1kg_*, hgdp_*, controls_* rows."),
        ] = False,
        include_sex_split: Annotated[
            bool,
            Field(description="Include _XX/_XY sex-split rows."),
        ] = False,
        exclude_zero_populations: Annotated[
            bool,
            Field(description="Drop populations with allele_count == 0."),
        ] = True,
    ) -> dict[str, Any]:
        """Use this when a caller has a fully-resolved CHROM-POS-REF-ALT id and needs allele counts/frequencies per population. Pair with get_clinvar_variant_details for clinical context. Compact defaults trim subcohort and zero-AC rows; toggle the boolean flags to expand. Returns a `truncated` block when filters drop rows so the LLM can re-call with explicit overrides."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            response = await service.get_variant_frequencies(variant_id, dataset)
            return shape_variant_frequencies(
                response,
                populations=populations,
                include_subcohorts=include_subcohorts,
                include_sex_split=include_sex_split,
                exclude_zero_populations=exclude_zero_populations,
            )

        return await run_mcp_tool(
            "get_variant_frequencies",
            call,
            context=McpErrorContext(
                tool_name="get_variant_frequencies",
                variant_id=variant_id,
                dataset=dataset,
            ),
        )

    @mcp.tool(
        name="get_variant_details",
        title="Get Variant Details",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=VariantDetails.model_json_schema(),
    )
    async def get_variant_details(
        variant_id: Annotated[
            str,
            Field(min_length=5, max_length=200, pattern=r"^[^'\"]+$"),
        ],
        dataset: Annotated[
            Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"], Field()
        ] = "gnomad_r4",
        response_mode: Annotated[
            Literal["compact", "full"],
            Field(description="compact strips raw GraphQL extras; full passes through everything."),
        ] = "compact",
    ) -> dict[str, Any]:
        """Use this when a caller needs transcript consequences, in-silico predictors, or ClinVar annotation for a single variant id. Prefer get_variant_frequencies if only allele counts are needed; this tool returns the larger annotation payload."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            raw = await service.get_variant(variant_id, dataset)
            if response_mode == "compact":
                return shape_variant_details_compact(raw)
            return raw

        return await run_mcp_tool(
            "get_variant_details",
            call,
            context=McpErrorContext(tool_name="get_variant_details", variant_id=variant_id, dataset=dataset),
        )
```

- [ ] **Step 2: Implement `genes.py`**

Create `gnomad_link/mcp/tools/genes.py`:

```python
"""Gene tools: get_gene_details, get_gene_variants."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool
from gnomad_link.mcp.shaping import shape_gene_variants
from gnomad_link.models import Gene
from gnomad_link.services import FrequencyService


def register_gene_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="get_gene_details",
        title="Get Gene Details",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=Gene.model_json_schema(),
    )
    async def get_gene_details(
        gene_id: Annotated[str | None, Field(description="Ensembl gene ID (preferred over symbol).")] = None,
        gene_symbol: Annotated[str | None, Field(description="HGNC gene symbol, used if gene_id is absent.")] = None,
        reference_genome: Annotated[Literal["GRCh37", "GRCh38"], Field()] = "GRCh38",
    ) -> dict[str, Any]:
        """Use this when a caller has a gene id or symbol and needs constraint scores (pLI/oe_lof), canonical transcript, and basic coordinates. Follow with get_gene_variants if they then need per-variant rows."""

        async def call() -> dict[str, Any]:
            if not gene_id and not gene_symbol:
                raise ValueError("Provide gene_id or gene_symbol.")
            service = service_factory()
            return await service.get_gene(
                gene_id=gene_id,
                gene_symbol=gene_symbol,
                reference_genome=reference_genome,
            )

        return await run_mcp_tool(
            "get_gene_details",
            call,
            context=McpErrorContext(
                tool_name="get_gene_details",
                gene_id=gene_id,
                gene_symbol=gene_symbol,
            ),
        )

    @mcp.tool(
        name="get_gene_variants",
        title="Get Gene Variants",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema={
            "type": "object",
            "properties": {
                "variants": {"type": "array", "items": {"type": "object"}},
                "returned": {"type": "integer"},
                "total_seen": {"type": "integer"},
                "truncated": {"type": ["object", "null"]},
            },
            "required": ["variants", "returned", "total_seen"],
            "additionalProperties": True,
        },
    )
    async def get_gene_variants(
        gene_id: Annotated[str, Field(description="Ensembl gene ID.")],
        dataset: Annotated[
            Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"], Field()
        ] = "gnomad_r4",
        limit: Annotated[int, Field(ge=1, le=500, description="Max variants returned (hard cap 500).")] = 100,
        consequence: Annotated[
            str | None,
            Field(description="VEP major_consequence to keep (e.g. 'missense_variant')."),
        ] = None,
        max_af: Annotated[
            float | None,
            Field(ge=0.0, le=1.0, description="Drop variants whose AF exceeds this threshold."),
        ] = None,
        min_ac: Annotated[int | None, Field(ge=0, description="Drop variants whose AC is below this threshold.")] = None,
    ) -> dict[str, Any]:
        """Use this when a caller wants per-variant rows inside a gene. Large genes (e.g. TTN) return tens of thousands of variants upstream; this tool caps at 500 and exposes consequence/AF/AC filters. Returns a `truncated` block whenever the cap fires."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            raw = await service.get_gene_variants(gene_id, dataset)
            return shape_gene_variants(
                raw,
                limit=limit,
                consequence=consequence,
                max_af=max_af,
                min_ac=min_ac,
            )

        return await run_mcp_tool(
            "get_gene_variants",
            call,
            context=McpErrorContext(
                tool_name="get_gene_variants",
                gene_id=gene_id,
                dataset=dataset,
            ),
        )
```

- [ ] **Step 3: Wire the registrations into the dispatcher**

Edit `gnomad_link/mcp/tools/__init__.py`:

```python
from gnomad_link.mcp.tools.genes import register_gene_tools
from gnomad_link.mcp.tools.metadata import register_metadata_tools
from gnomad_link.mcp.tools.variants import register_variant_tools


def register_gnomad_tools(
    mcp: FastMCP,
    *,
    service_factory: Callable[[], FrequencyService],
) -> None:
    register_metadata_tools(mcp)
    register_variant_tools(mcp, service_factory=service_factory)
    register_gene_tools(mcp, service_factory=service_factory)
```

- [ ] **Step 4: Run focused surface tests for these four tools**

```bash
uv run pytest tests/unit/mcp/ -q
```

Expected: 4 tools (variants×2, genes×2 plus capabilities) present; remaining tools still missing.

- [ ] **Step 5: Commit**

```bash
git add gnomad_link/mcp/tools/variants.py gnomad_link/mcp/tools/genes.py gnomad_link/mcp/tools/__init__.py
git commit -m "feat(mcp): register variant and gene tools with output schemas"
```

---

### Task 8: Register Data Tools (ClinVar + Coordinates + Specialty + Search)

**Files:**
- Create: `gnomad_link/mcp/tools/clinvar.py`
- Create: `gnomad_link/mcp/tools/coordinates.py`
- Create: `gnomad_link/mcp/tools/specialty.py`
- Create: `gnomad_link/mcp/tools/search.py`
- Modify: `gnomad_link/mcp/tools/__init__.py`

- [ ] **Step 1: Implement `clinvar.py`**

Create `gnomad_link/mcp/tools/clinvar.py`:

```python
"""ClinVar tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool
from gnomad_link.models import ClinVarVariant
from gnomad_link.services import FrequencyService


def register_clinvar_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="get_clinvar_variant_details",
        title="Get ClinVar Variant",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=ClinVarVariant.model_json_schema(),
    )
    async def get_clinvar_variant_details(
        variant_id: Annotated[str, Field(min_length=5, max_length=200, pattern=r"^[^'\"]+$")],
        reference_genome: Annotated[Literal["GRCh37", "GRCh38"], Field()] = "GRCh38",
    ) -> dict[str, Any]:
        """Use this when a caller needs ClinVar clinical significance, review status, gold stars, or submissions for a single variant id. Complementary to get_variant_frequencies for clinical workflows."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            return await service.get_clinvar_variant(variant_id, reference_genome)

        return await run_mcp_tool(
            "get_clinvar_variant_details",
            call,
            context=McpErrorContext(
                tool_name="get_clinvar_variant_details", variant_id=variant_id
            ),
        )

    @mcp.tool(
        name="get_clinvar_meta",
        title="Get ClinVar Metadata",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema={"type": "object", "additionalProperties": True},
    )
    async def get_clinvar_meta() -> dict[str, Any]:
        """Use this when a caller only needs the ClinVar release date or revision currently served by gnomAD — cheaper than full capabilities."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            return await service.get_clinvar_meta()

        return await run_mcp_tool(
            "get_clinvar_meta",
            call,
            context=McpErrorContext(tool_name="get_clinvar_meta"),
        )
```

- [ ] **Step 2: Implement `coordinates.py`**

Create `gnomad_link/mcp/tools/coordinates.py`:

```python
"""Liftover and region tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool
from gnomad_link.mcp.shaping import cap_region_span
from gnomad_link.models import LiftoverResponse, Region
from gnomad_link.services import FrequencyService

_REGION_PATTERN = r"^(chr)?([1-9]|1[0-9]|2[0-2]|X|Y|M|MT)-\d+-\d+$"


def register_coordinate_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="liftover_variant",
        title="Liftover Variant Between GRCh37 and GRCh38",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=LiftoverResponse.model_json_schema(),
    )
    async def liftover_variant(
        source_variant_id: Annotated[
            str,
            Field(description="Variant ID to convert (CHROM-POS-REF-ALT)."),
        ],
        reference_genome: Annotated[
            Literal["GRCh37", "GRCh38"],
            Field(description="Reference build of source_variant_id."),
        ],
    ) -> dict[str, Any]:
        """Use this when a caller has a variant id in one reference build and needs the equivalent id in the other. Use this BEFORE calling frequency tools if the dataset and coordinate build do not match."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            results = await service.liftover_variant(source_variant_id, reference_genome)
            return {"results": results, "source_variant_id": source_variant_id, "source_reference_genome": reference_genome}

        return await run_mcp_tool(
            "liftover_variant",
            call,
            context=McpErrorContext(
                tool_name="liftover_variant", variant_id=source_variant_id
            ),
        )

    @mcp.tool(
        name="get_region",
        title="Get Variants and Genes in a Region",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=Region.model_json_schema(),
    )
    async def get_region(
        region: Annotated[
            str,
            Field(description="Region in chr-start-stop format (e.g. 17-7674232-7674252).", pattern=_REGION_PATTERN),
        ],
        dataset: Annotated[
            Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"], Field()
        ] = "gnomad_r4",
        include_clinvar: Annotated[bool, Field(description="Include ClinVar variants in the region.")] = True,
        include_genes: Annotated[bool, Field(description="Include overlapping genes.")] = True,
    ) -> dict[str, Any]:
        """Use this when a caller wants genes and/or ClinVar variants in a small region (≤100kb). Spans larger than 100kb are clamped and a `truncated` block reports it. For per-variant SNV listings use get_gene_variants instead."""

        async def call() -> dict[str, Any]:
            chrom, start_s, stop_s = region.removeprefix("chr").split("-")
            start, stop = int(start_s), int(stop_s)
            if stop <= start:
                raise ValueError("Region stop must be greater than start.")
            adj_start, adj_stop, capped = cap_region_span(chrom, start, stop)
            service = service_factory()
            raw = await service.get_region(chrom, adj_start, adj_stop, dataset)
            payload = raw.get("region", raw) if isinstance(raw, dict) else raw
            if isinstance(payload, dict):
                if not include_clinvar:
                    payload.pop("clinvar_variants", None)
                if not include_genes:
                    payload.pop("genes", None)
                if capped:
                    payload["truncated"] = {
                        "kind": "region_span",
                        "requested_bp": stop - start,
                        "served_bp": adj_stop - adj_start,
                        "to_disable": "request smaller windows; max 100kb per call",
                    }
            return payload

        return await run_mcp_tool(
            "get_region",
            call,
            context=McpErrorContext(tool_name="get_region", region=region, dataset=dataset),
        )
```

- [ ] **Step 3: Implement `specialty.py`**

Create `gnomad_link/mcp/tools/specialty.py`:

```python
"""Structural variant, mitochondrial variant, and transcript tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool
from gnomad_link.models import MitochondrialVariant, StructuralVariant, Transcript
from gnomad_link.services import FrequencyService


def register_specialty_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="get_structural_variant",
        title="Get Structural Variant",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=StructuralVariant.model_json_schema(),
    )
    async def get_structural_variant(
        variant_id: Annotated[str, Field(description="gnomAD SV identifier.", min_length=3, max_length=200)],
        dataset: Annotated[
            Literal["gnomad_sv_r2_1", "gnomad_sv_r4"], Field()
        ] = "gnomad_sv_r4",
    ) -> dict[str, Any]:
        """Use this when a caller has a gnomAD structural variant id (deletions, duplications, inversions, BNDs). For SNVs/indels use get_variant_frequencies instead."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            raw = await service.get_structural_variant(variant_id, dataset)
            return raw.get("structural_variant", raw) if isinstance(raw, dict) else raw

        return await run_mcp_tool(
            "get_structural_variant",
            call,
            context=McpErrorContext(
                tool_name="get_structural_variant", variant_id=variant_id, dataset=dataset
            ),
        )

    @mcp.tool(
        name="get_mitochondrial_variant",
        title="Get Mitochondrial Variant",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=MitochondrialVariant.model_json_schema(),
    )
    async def get_mitochondrial_variant(
        variant_id: Annotated[
            str,
            Field(description="Mitochondrial variant in M-POS-REF-ALT format.", min_length=5, max_length=100),
        ],
        dataset: Annotated[
            Literal["gnomad_r3", "gnomad_r4"], Field()
        ] = "gnomad_r4",
    ) -> dict[str, Any]:
        """Use this when a caller has a mitochondrial variant id (M-POS-REF-ALT). Mitochondrial ploidy and heteroplasmy fields are returned; for autosomal variants use get_variant_frequencies."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            raw = await service.get_mitochondrial_variant(variant_id, dataset)
            return raw.get("mitochondrial_variant", raw) if isinstance(raw, dict) else raw

        return await run_mcp_tool(
            "get_mitochondrial_variant",
            call,
            context=McpErrorContext(
                tool_name="get_mitochondrial_variant", variant_id=variant_id, dataset=dataset
            ),
        )

    @mcp.tool(
        name="get_transcript_details",
        title="Get Transcript Details",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=Transcript.model_json_schema(),
    )
    async def get_transcript_details(
        transcript_id: Annotated[str, Field(description="Ensembl transcript ID (ENST…)", min_length=4, max_length=80)],
        reference_genome: Annotated[Literal["GRCh37", "GRCh38"], Field()] = "GRCh38",
    ) -> dict[str, Any]:
        """Use this when a caller has an Ensembl transcript id and needs exon structure or GTEx tissue expression. For gene-level info use get_gene_details."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            return await service.get_transcript(transcript_id, reference_genome)

        return await run_mcp_tool(
            "get_transcript_details",
            call,
            context=McpErrorContext(tool_name="get_transcript_details"),
        )
```

- [ ] **Step 4: Implement `search.py`**

Create `gnomad_link/mcp/tools/search.py`:

```python
"""Search and identifier-resolution tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool
from gnomad_link.models import GeneSearchResult, VariantSearchResult
from gnomad_link.services import FrequencyService


def register_search_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="search_genes",
        title="Search Genes",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema={
            "type": "object",
            "properties": {
                "results": {"type": "array", "items": GeneSearchResult.model_json_schema()},
                "returned": {"type": "integer"},
                "truncated": {"type": ["object", "null"]},
            },
            "required": ["results", "returned"],
        },
    )
    async def search_genes(
        query: Annotated[str, Field(min_length=2, max_length=100, description="Gene symbol, name fragment, or Ensembl ID.")],
        reference_genome: Annotated[Literal["GRCh37", "GRCh38"], Field()] = "GRCh38",
        limit: Annotated[int, Field(ge=1, le=50, description="Max matches returned.")] = 25,
    ) -> dict[str, Any]:
        """Use this when a caller has a fuzzy gene query (symbol, alias, partial name). Follow with get_gene_details for full constraint metrics."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            raw = await service.client.search_genes(query, reference_genome)
            total = len(raw)
            results = raw[:limit]
            payload: dict[str, Any] = {"results": results, "returned": len(results)}
            if total > len(results):
                payload["truncated"] = {
                    "kind": "search_results",
                    "total_seen": total,
                    "to_disable": "raise limit (max 50) or refine the query",
                }
            return payload

        return await run_mcp_tool(
            "search_genes",
            call,
            context=McpErrorContext(tool_name="search_genes"),
        )

    @mcp.tool(
        name="resolve_variant_id",
        title="Resolve Variant Identifier",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema={
            "type": "object",
            "properties": {
                "results": {"type": "array", "items": VariantSearchResult.model_json_schema()},
                "returned": {"type": "integer"},
                "next_steps": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["results", "returned", "next_steps"],
        },
    )
    async def resolve_variant_id(
        query: Annotated[
            str,
            Field(min_length=3, max_length=100, description="rsID, CHROM-POS-REF-ALT, or 'CHROM:POS'."),
        ],
        dataset: Annotated[
            Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"], Field()
        ] = "gnomad_r4",
        limit: Annotated[int, Field(ge=1, le=25)] = 10,
    ) -> dict[str, Any]:
        """Use this when the caller only has an rsID, partial coordinates, or text fragment and needs to obtain a canonical gnomAD variant id. Returns IDs only — call get_variant_frequencies or get_variant_details next."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            raw = await service.search_variants(query, dataset)
            results = raw[:limit]
            return {
                "results": results,
                "returned": len(results),
                "next_steps": [
                    "Pick one variant_id and call get_variant_frequencies(variant_id, dataset).",
                    "Or call get_variant_details(variant_id, dataset) for annotations.",
                ],
            }

        return await run_mcp_tool(
            "resolve_variant_id",
            call,
            context=McpErrorContext(tool_name="resolve_variant_id"),
        )

    @mcp.tool(
        name="search_variants",
        title="Search Variants (deprecated alias)",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema={
            "type": "object",
            "properties": {
                "results": {"type": "array", "items": VariantSearchResult.model_json_schema()},
                "returned": {"type": "integer"},
                "next_steps": {"type": "array", "items": {"type": "string"}},
                "_meta": {"type": "object"},
            },
            "required": ["results", "returned", "next_steps"],
        },
    )
    async def search_variants(
        query: Annotated[str, Field(min_length=3, max_length=100)],
        dataset: Annotated[
            Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"], Field()
        ] = "gnomad_r4",
        limit: Annotated[int, Field(ge=1, le=25)] = 10,
    ) -> dict[str, Any]:
        """Use this when a caller uses the legacy tool name — deprecated alias for resolve_variant_id. Same behaviour; will be removed in the next release."""

        async def call() -> dict[str, Any]:
            service = service_factory()
            raw = await service.search_variants(query, dataset)
            results = raw[:limit]
            return {
                "results": results,
                "returned": len(results),
                "next_steps": [
                    "Pick one variant_id and call get_variant_frequencies(variant_id, dataset).",
                ],
                "_meta": {"deprecated": True, "use_instead": "resolve_variant_id"},
            }

        return await run_mcp_tool(
            "search_variants",
            call,
            context=McpErrorContext(tool_name="search_variants"),
        )
```

- [ ] **Step 5: Wire all registrations**

Replace `gnomad_link/mcp/tools/__init__.py` body:

```python
from gnomad_link.mcp.tools.clinvar import register_clinvar_tools
from gnomad_link.mcp.tools.coordinates import register_coordinate_tools
from gnomad_link.mcp.tools.genes import register_gene_tools
from gnomad_link.mcp.tools.metadata import register_metadata_tools
from gnomad_link.mcp.tools.search import register_search_tools
from gnomad_link.mcp.tools.specialty import register_specialty_tools
from gnomad_link.mcp.tools.variants import register_variant_tools


def register_gnomad_tools(
    mcp: FastMCP,
    *,
    service_factory: Callable[[], FrequencyService],
) -> None:
    register_metadata_tools(mcp)
    register_variant_tools(mcp, service_factory=service_factory)
    register_gene_tools(mcp, service_factory=service_factory)
    register_clinvar_tools(mcp, service_factory=service_factory)
    register_coordinate_tools(mcp, service_factory=service_factory)
    register_specialty_tools(mcp, service_factory=service_factory)
    register_search_tools(mcp, service_factory=service_factory)
```

- [ ] **Step 6: Run the full surface test suite**

```bash
uv run pytest tests/unit/mcp/ -q
```

Expected: all surface, capability, error, shaping, and large-response tests PASS.

- [ ] **Step 7: Commit**

```bash
git add gnomad_link/mcp/tools/
git commit -m "feat(mcp): register clinvar, coordinates, specialty, and search tools"
```

---

### Task 9: Wire The Facade Into `UnifiedServerManager` And Strip REST

**Files:**
- Modify: `gnomad_link/server_manager.py`
- Modify: `gnomad_link/api/__init__.py`
- Modify: `gnomad_link/api/routes/__init__.py`
- Delete: `gnomad_link/api/routes/clinvar.py`, `gene.py`, `liftover.py`, `mitochondrial.py`, `region.py`, `search.py`, `structural_variant.py`, `transcript.py`, `variant.py`
- Delete: `gnomad_link/api/routes/dependencies.py`
- Modify: `tests/unit/test_server_manager.py`
- Test: `tests/unit/mcp/test_mcp_client_smoke.py`

- [ ] **Step 1: Write an in-process FastMCP smoke test**

Create `tests/unit/mcp/test_mcp_client_smoke.py`:

```python
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from gnomad_link.mcp.facade import create_gnomad_mcp


@pytest.mark.asyncio
async def test_in_process_client_lists_tools_and_reads_capabilities() -> None:
    service = AsyncMock()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    assert {"get_server_capabilities", "get_variant_frequencies", "resolve_variant_id"} <= names

    result = await mcp.call_tool("get_server_capabilities", {})
    payload = result.structured_content or {}
    assert payload["server"] == "gnomad-link"
    assert "datasets" in payload
    assert "recommended_workflows" in payload


@pytest.mark.asyncio
async def test_in_process_client_reads_capabilities_resource() -> None:
    service = AsyncMock()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    contents = await mcp.read_resource("gnomad://capabilities")
    assert contents
```

- [ ] **Step 2: Rewrite `server_manager.py`**

Replace the file with the slimmer manager (keep imports, signal handlers, lifespan composition). The full new content:

```python
"""Unified server manager for gnomAD Link."""

from __future__ import annotations

import asyncio
import signal
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP

from gnomad_link.api.client import UnifiedGnomadClient
from gnomad_link.config import ServerConfig, settings
from gnomad_link.exceptions import ConfigurationError, MCPIntegrationError, StartupError
from gnomad_link.logging_config import configure_logging, get_server_logger
from gnomad_link.mcp.facade import create_gnomad_mcp
from gnomad_link.services.frequency_service import FrequencyService


class UnifiedServerManager:
    def __init__(self) -> None:
        self.app: FastAPI | None = None
        self.mcp: FastMCP | None = None
        self.shutdown_event = asyncio.Event()
        self.logger = None
        self._current_transport = "unknown"

    # ---------------- service factory helpers ----------------

    def _create_frequency_service(self) -> FrequencyService:
        api_client = UnifiedGnomadClient()
        return FrequencyService(
            client=api_client,
            cache_size=settings.CACHE_SIZE,
            cache_ttl_minutes=settings.CACHE_TTL_MINUTES,
        )

    # ---------------- FastAPI host (health only) ----------------

    async def _create_fastapi_app(self, config: ServerConfig) -> FastAPI:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            self.logger.info("Starting gnomAD Link host application...")
            app.state.frequency_service = self._create_frequency_service()
            self.logger.info("Service ready")
            yield
            self.logger.info("Shutting down host application...")

        app = FastAPI(
            title="gnomAD Link MCP Host",
            description="Thin FastAPI host that exposes /health and mounts the MCP HTTP app at /mcp.",
            version="5.0.0",
            lifespan=lifespan,
            docs_url=None,
            redoc_url=None,
            openapi_url=None,
        )
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @app.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "healthy", "transport": self._current_transport}

        return app

    # ---------------- MCP creation ----------------

    def _create_mcp_server(
        self, service_factory: Callable[[], FrequencyService]
    ) -> FastMCP:
        try:
            mcp = create_gnomad_mcp(service_factory=service_factory)
            self.logger.info("MCP facade created")
            return mcp
        except Exception as e:
            raise MCPIntegrationError(f"Failed to create MCP server: {e}", "mcp") from e

    @staticmethod
    def _compose_lifespan(app: FastAPI, mcp_app) -> None:
        fastapi_lifespan = app.router.lifespan_context
        mcp_lifespan = mcp_app.lifespan

        @asynccontextmanager
        async def combined(parent_app: FastAPI):
            async with fastapi_lifespan(parent_app):
                async with mcp_lifespan(mcp_app):
                    yield

        app.router.lifespan_context = combined

    # ---------------- signal handlers ----------------

    def _setup_signal_handlers(self) -> None:
        def handler(signum, _frame) -> None:
            self.logger.info(f"Received signal {signum}; shutting down...")
            self.shutdown_event.set()

        signal.signal(signal.SIGTERM, handler)
        signal.signal(signal.SIGINT, handler)

    # ---------------- entry points ----------------

    async def start_unified_server(self, config: ServerConfig) -> None:
        try:
            self._current_transport = "unified"
            configure_logging("unified", config.log_level)
            self.logger = get_server_logger("unified")

            self.app = await self._create_fastapi_app(config)

            def service_factory() -> FrequencyService:
                if self.app is None:
                    raise RuntimeError("FastAPI host not initialized")
                return self.app.state.frequency_service

            self.mcp = self._create_mcp_server(service_factory)
            mcp_http_app = self.mcp.http_app(path="/", stateless_http=True, json_response=True)
            self._compose_lifespan(self.app, mcp_http_app)
            self.app.mount(config.mcp_path, mcp_http_app)

            self.logger.info(f"MCP HTTP at http://{config.host}:{config.port}{config.mcp_path}")
            self.logger.info(f"Health at http://{config.host}:{config.port}/health")

            self._setup_signal_handlers()

            uvicorn_config = uvicorn.Config(
                app=self.app, host=config.host, port=config.port,
                log_level=config.log_level.lower(), access_log=True,
            )
            await uvicorn.Server(uvicorn_config).serve()
        except Exception as e:
            raise StartupError(f"Failed to start unified server: {e}", "unified") from e

    async def start_stdio_server(self, config: ServerConfig) -> None:
        try:
            self._current_transport = "stdio"
            configure_logging("stdio", config.log_level)
            self.logger = get_server_logger("stdio")

            service = self._create_frequency_service()
            self.mcp = self._create_mcp_server(lambda: service)
            await self.mcp.run_async(transport="stdio")
        except Exception as e:
            raise StartupError(f"Failed to start STDIO server: {e}", "stdio") from e

    async def start_server(self, config: ServerConfig) -> None:
        if config.transport in {"unified", "http"}:
            await self.start_unified_server(config)
        elif config.transport == "stdio":
            await self.start_stdio_server(config)
        else:
            raise ConfigurationError(f"Unknown transport: {config.transport}")
```

Notes:
- `http` transport now aliases `unified`; the standalone REST-only mode is gone because there are no REST routes left to serve.
- `/cache/clear` and `/cache/stats` REST endpoints are removed; Task 10 adds them as CLI subcommands.

- [ ] **Step 3: Delete the REST routers**

```bash
git rm \
  gnomad_link/api/routes/clinvar.py \
  gnomad_link/api/routes/gene.py \
  gnomad_link/api/routes/liftover.py \
  gnomad_link/api/routes/mitochondrial.py \
  gnomad_link/api/routes/region.py \
  gnomad_link/api/routes/search.py \
  gnomad_link/api/routes/structural_variant.py \
  gnomad_link/api/routes/transcript.py \
  gnomad_link/api/routes/variant.py \
  gnomad_link/api/routes/dependencies.py
```

- [ ] **Step 4: Trim route package init**

Replace `gnomad_link/api/routes/__init__.py` with:

```python
"""REST routes have been removed; MCP is the primary interface.

This file is intentionally empty and retained only so the import path stays
stable for downstream tooling. Remove the directory entirely in a follow-up
release.
"""
```

- [ ] **Step 5: Rewrite `tests/unit/test_server_manager.py`**

Replace assertions that grep for `FastMCP.from_fastapi` with:

```python
import pytest

from gnomad_link.server_manager import UnifiedServerManager


def test_server_manager_uses_facade(monkeypatch) -> None:
    import gnomad_link.server_manager as sm

    called = {}

    def fake_create(*, service_factory):
        called["service_factory"] = service_factory
        return object()

    monkeypatch.setattr(sm, "create_gnomad_mcp", fake_create)
    manager = UnifiedServerManager()
    manager.logger = type("L", (), {"info": lambda *a, **k: None})()
    mcp = manager._create_mcp_server(lambda: None)
    assert mcp is not None
    assert callable(called["service_factory"])


def test_server_manager_no_longer_imports_fastmcp_from_fastapi() -> None:
    import inspect
    import gnomad_link.server_manager as sm

    source = inspect.getsource(sm)
    assert "from_fastapi" not in source
    assert "mcp_custom_names" not in source
    assert "RouteMap" not in source
```

- [ ] **Step 6: Run the full unit suite**

```bash
uv run pytest tests/unit/ -q
```

Expected: all unit tests PASS. Integration tests still reference deleted REST routes — Task 11 deletes them.

- [ ] **Step 7: Commit**

```bash
git add gnomad_link/server_manager.py gnomad_link/api/routes/ tests/unit/test_server_manager.py tests/unit/mcp/test_mcp_client_smoke.py
git commit -m "feat(mcp): mount hand-authored facade and drop REST routes"
```

---

### Task 10: Move Cache Management And Health Off REST Into CLI

**Files:**
- Modify: `gnomad_link/cli.py`
- Test: `tests/unit/test_cli_cache_commands.py`

The `/cache/stats` and `/cache/clear` REST endpoints are gone. They become CLI subcommands so operators retain a way to inspect/wipe the in-process cache (used when running stdio or a long-lived HTTP instance with shell access).

- [ ] **Step 1: Inspect current CLI to determine framework (Click/Typer/argparse)**

Read `gnomad_link/cli.py` and confirm the CLI library before writing tests.

- [ ] **Step 2: Write failing CLI tests**

Create `tests/unit/test_cli_cache_commands.py` using the framework you found. Example for Typer:

```python
from __future__ import annotations

from typer.testing import CliRunner

from gnomad_link.cli import app

runner = CliRunner()


def test_cache_stats_prints_table() -> None:
    result = runner.invoke(app, ["cache", "stats"])
    assert result.exit_code == 0
    assert "cache_size" in result.stdout.lower() or "size" in result.stdout.lower()


def test_cache_clear_succeeds() -> None:
    result = runner.invoke(app, ["cache", "clear"])
    assert result.exit_code == 0
    assert "cleared" in result.stdout.lower()
```

- [ ] **Step 3: Run and confirm failure**

```bash
uv run pytest tests/unit/test_cli_cache_commands.py -q
```

Expected: command-not-found from the CLI runner.

- [ ] **Step 4: Add the subcommands to `cli.py`**

Append cache subcommands that construct an in-process service via `UnifiedServerManager._create_frequency_service`, call `get_cache_stats()` or `clear_cache()`, and print results. Use whichever CLI framework already lives in this file.

- [ ] **Step 5: Run the CLI tests**

```bash
uv run pytest tests/unit/test_cli_cache_commands.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add gnomad_link/cli.py tests/unit/test_cli_cache_commands.py
git commit -m "feat(cli): expose cache stats/clear via CLI in place of removed REST"
```

---

### Task 11: Convert Integration Tests To MCP Client Tests

**Files:**
- Delete: `tests/integration/test_variant_endpoints.py`, `test_gene_endpoints.py`, `test_clinvar_endpoints.py`, `test_structural_variant_endpoints.py`, `test_region_endpoints.py`, `test_mitochondrial_endpoints.py`, `test_liftover_endpoints.py`, `test_transcript_endpoints.py`, `test_search_endpoints.py`
- Create: `tests/integration/test_mcp_live_tools.py`
- Modify: `tests/integration/conftest.py` (or create if missing)

- [ ] **Step 1: Inventory the existing assertions**

Read each `tests/integration/test_*_endpoints.py` and capture the live-API assertions (variant IDs, expected fields). Most assertions are about response structure on a known-stable variant such as `1-55051215-G-GA`.

- [ ] **Step 2: Create the replacement integration test**

Create `tests/integration/test_mcp_live_tools.py`:

```python
"""Live MCP tool tests against the gnomAD upstream. Gated by the `integration` marker."""

from __future__ import annotations

import pytest

from gnomad_link.api.client import UnifiedGnomadClient
from gnomad_link.mcp.facade import create_gnomad_mcp
from gnomad_link.services.frequency_service import FrequencyService

pytestmark = pytest.mark.integration


@pytest.fixture
def mcp_with_live_service():
    service = FrequencyService(client=UnifiedGnomadClient())
    return create_gnomad_mcp(service_factory=lambda: service)


@pytest.mark.asyncio
async def test_get_variant_frequencies_live(mcp_with_live_service) -> None:
    result = await mcp_with_live_service.call_tool(
        "get_variant_frequencies",
        {"variant_id": "1-55051215-G-GA", "dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}
    assert payload["variant_id"] == "1-55051215-G-GA"
    assert payload["exome"] is not None
    afr = next(p for p in payload["exome"]["populations"] if p["id"] == "afr")
    assert afr["af"] > 0.01


@pytest.mark.asyncio
async def test_get_gene_details_live(mcp_with_live_service) -> None:
    result = await mcp_with_live_service.call_tool(
        "get_gene_details", {"gene_symbol": "PCSK9"}
    )
    payload = result.structured_content or {}
    assert payload["symbol"] == "PCSK9"
    assert payload["constraint"]["pLI"] is not None


@pytest.mark.asyncio
async def test_resolve_variant_id_returns_ids_only(mcp_with_live_service) -> None:
    result = await mcp_with_live_service.call_tool(
        "resolve_variant_id", {"query": "rs11591147"}
    )
    payload = result.structured_content or {}
    assert payload["returned"] >= 1
    for r in payload["results"]:
        assert "variant_id" in r


@pytest.mark.asyncio
async def test_get_region_caps_span(mcp_with_live_service) -> None:
    result = await mcp_with_live_service.call_tool(
        "get_region", {"region": "1-55000000-56000000"}
    )
    payload = result.structured_content or {}
    assert payload.get("truncated", {}).get("kind") == "region_span"


@pytest.mark.asyncio
async def test_get_gene_variants_caps_at_limit(mcp_with_live_service) -> None:
    result = await mcp_with_live_service.call_tool(
        "get_gene_variants", {"gene_id": "ENSG00000155657", "limit": 50}  # TTN
    )
    payload = result.structured_content or {}
    assert payload["returned"] == 50
    assert payload.get("truncated", {}).get("kind") == "gene_variants"
```

- [ ] **Step 3: Delete the obsolete REST integration tests**

```bash
git rm tests/integration/test_variant_endpoints.py \
       tests/integration/test_gene_endpoints.py \
       tests/integration/test_clinvar_endpoints.py \
       tests/integration/test_structural_variant_endpoints.py \
       tests/integration/test_region_endpoints.py \
       tests/integration/test_mitochondrial_endpoints.py \
       tests/integration/test_liftover_endpoints.py \
       tests/integration/test_transcript_endpoints.py \
       tests/integration/test_search_endpoints.py
```

- [ ] **Step 4: Run integration tests against the live API**

```bash
uv run pytest tests/integration/test_mcp_live_tools.py -m integration -q
```

Expected: PASS (or upstream-rate-limit related skips; do not retry blindly).

- [ ] **Step 5: Commit**

```bash
git add tests/integration/
git commit -m "test: replace REST integration tests with MCP live-tool tests"
```

---

### Task 12: Update Docker, Makefile, Configuration

**Files:**
- Modify: `docker/Dockerfile`
- Modify: `docker/docker-compose.yml` (and overlays as needed)
- Modify: `Makefile`
- Modify: `gnomad_link/config.py` (only if transport enum changes)

- [ ] **Step 1: Update Dockerfile healthcheck if present**

Confirm Dockerfile keeps `/health` as the healthcheck endpoint (the only REST route left). No source change needed unless an existing `HEALTHCHECK` line references `/docs`.

- [ ] **Step 2: Update Compose healthcheck**

In `docker/docker-compose.yml`, confirm `healthcheck.test` hits `/health` (likely already correct). Remove any reference to `/docs`, `/cache/stats`, or `/openapi.json`.

- [ ] **Step 3: Update Makefile targets**

Edit `Makefile`:

- Remove `mcp-serve-http` if it is just an alias; otherwise update it to call the unified entry point.
- Update `dev` target docstring to say "FastAPI host (/health) + mounted MCP HTTP".
- Drop any target that runs `--transport http` only; the transport flag still accepts `http` but it now behaves identically to `unified`.

- [ ] **Step 4: Verify config still accepts the same transports**

Read `gnomad_link/config.py`. If `transport` is constrained to `{"stdio", "http", "unified"}`, leave it alone — `start_server` now treats `http` as `unified`.

- [ ] **Step 5: Smoke the Docker build**

```bash
make docker-build
make docker-up
curl -fsS http://127.0.0.1:8020/health
```

Expected: `{"status":"healthy",...}`.

Then verify MCP works in the container:

```bash
uv run python - <<'PY'
import asyncio
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "http://127.0.0.1:8020/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Accept": "application/json, text/event-stream"},
        )
        print(r.status_code, r.text[:400])

asyncio.run(main())
PY
```

Expected: HTTP 200 and a JSON-RPC response listing tools.

```bash
make docker-down
```

- [ ] **Step 6: Commit**

```bash
git add docker/ Makefile gnomad_link/config.py
git commit -m "chore: align docker and make targets with mcp-first server"
```

---

### Task 13: Documentation Refresh

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md` (only if it explicitly mentions REST)
- Modify: `docs/architecture.md`
- Modify: `docs/usage.md`
- Modify: `docs/MCP_CONNECTION_GUIDE.md`
- Delete: `docs/api-reference.md`
- Modify: `docs/superpowers/specs/2026-05-25-mcp-facade-migration-design.md` (update Non-Goals)

- [ ] **Step 1: README**

Rewrite the "Quickstart" and "Endpoints" sections to lead with MCP. Replace REST curl examples with MCP HTTP examples:

```bash
curl -sS http://127.0.0.1:8020/mcp \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Add a Claude Code install line:

```bash
claude mcp add --transport http gnomad-link http://127.0.0.1:8020/mcp
```

- [ ] **Step 2: AGENTS.md**

Update the project description to say "MCP server for gnomAD; FastAPI is a thin host providing /health only." Add to the Working Rules section: "MCP tool names, schemas, resources, and response modes are owned by `gnomad_link/mcp/`. REST is intentionally minimal (`/health` only)."

- [ ] **Step 3: Architecture doc**

Edit `docs/architecture.md`. Replace the "REST API for web clients" section with: "FastAPI host: serves `/health` only and mounts the FastMCP HTTP app at `/mcp`. All domain functionality is exposed via MCP."

- [ ] **Step 4: Usage doc**

Edit `docs/usage.md`. Replace each curl example with the equivalent MCP tool invocation (Python snippet using `fastmcp.Client` or `claude mcp call`). Drop the `/api/*` section.

- [ ] **Step 5: MCP connection guide**

Confirm `docs/MCP_CONNECTION_GUIDE.md` is current. Add a section on Claude Code, Claude Desktop, and stdio integration; note that the deprecated `search_variants` will be removed.

- [ ] **Step 6: Delete the REST reference doc**

```bash
git rm docs/api-reference.md
```

- [ ] **Step 7: Spec doc Non-Goals update**

Edit `docs/superpowers/specs/2026-05-25-mcp-facade-migration-design.md`. Replace the Non-Goals lines that said "Do not remove FastAPI, REST routes, /docs, or /openapi.json" and "Do not change public REST paths" with:

```
- The REST surface is intentionally reduced to /health only.
- /docs, /redoc, /openapi.json, and all /variant /gene /clinvar etc. routes are removed.
- /cache/stats and /cache/clear move to the CLI.
- search_variants becomes a deprecated alias for resolve_variant_id; one-release removal window.
```

Also update the Architecture diagram to drop the REST/OpenAPI facade line and add a single "FastAPI /health host" box.

- [ ] **Step 8: Commit**

```bash
git add README.md AGENTS.md CLAUDE.md docs/
git commit -m "docs: document mcp-first architecture and removal of rest surface"
```

---

### Task 14: Final Verification

**Files:** none (verification only)

- [ ] **Step 1: Format**

```bash
make format
```

- [ ] **Step 2: Full local CI**

```bash
make ci-local
```

Expected: Ruff, line-budget, mypy, and unit tests pass.

- [ ] **Step 3: Live integration smoke (out of CI)**

```bash
uv run pytest tests/integration/ -m integration -q
```

Expected: PASS or rate-limit related skips.

- [ ] **Step 4: Container end-to-end**

```bash
make docker-build && make docker-up
sleep 5
curl -fsS http://127.0.0.1:8020/health
uv run python - <<'PY'
import asyncio
from fastmcp import Client

async def main():
    async with Client("http://127.0.0.1:8020/mcp") as c:
        tools = await c.list_tools()
        names = {t.name for t in tools}
        print(sorted(names))
        assert "get_variant_frequencies" in names
        result = await c.call_tool("get_server_capabilities", {})
        print(result.structured_content["server"])

asyncio.run(main())
PY
make docker-down
```

- [ ] **Step 5: Final commit**

If `make format` produced changes:

```bash
git add -u
git commit -m "chore: apply ruff formatting after migration"
```

- [ ] **Step 6: Tag**

```bash
git tag -a v5.0.0-mcp-facade -m "MCP-first facade migration"
```

(Do not push; user controls remote operations.)

---

## Self-Review Checklist (for the executor before claiming done)

Run mentally before declaring victory:

1. **Surface tests green:** every tool in `EXPECTED_TOOLS` is registered, named correctly, annotated, has an output schema, and its description starts with "Use this when".
2. **No silent truncation:** `get_variant_frequencies` populations response from `1-55051215-G-GA` is fully accounted for — every dropped row is reflected in the `truncated.dropped` counters; no client-side truncation flags appear without source-code origin.
3. **Error envelopes:** every tool dispatches through `run_mcp_tool`. Triggering a `ValueError`, `DataNotFoundError`, and `GnomadApiError` each produces the expected `error_code`.
4. **REST gone, /health stays:** `curl http://localhost:8020/variant/...` returns 404; `curl http://localhost:8020/health` returns 200.
5. **CLI cache subcommands exist:** `gnomad-link cache stats` and `gnomad-link cache clear` print sensible output.
6. **Docker healthcheck passes** with the new minimal FastAPI host.
7. **Docs updated:** README quickstart shows MCP, not REST; `api-reference.md` is gone; spec Non-Goals reflect the new direction.
8. **No grandfathered allowlist growth:** `.loc-allowlist` is not extended unless explicitly justified.
