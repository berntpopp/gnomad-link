# Phase C — Five New MCP Tools Implementation Plan

> Historical record

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the five tools deferred from the LLM-consumer review / facade-polish "Out of Scope" list — `get_coverage`, `compare_variant_across_datasets`, `compute_carrier_frequency`, `get_gene_summary`, `search_structural_variants` — taking the hand-authored MCP facade from 16 to 21 tools without breaking any existing invariant.

**Architecture:** Each tool is one `@mcp.tool` inside a new `register_<area>_tools(mcp, *, service_factory)` module wired into `gnomad_link/mcp/tools/__init__.py`. Two tools are pure local composition over the existing `FrequencyService.get_variant_frequencies` (C2 compare, C3 carrier); one extends the gene query (C4); two add new coverage / structural-variant GraphQL surface (C1, C5). New GraphQL docs live in `queries/common/`, new query-exec methods on `UnifiedGnomadClient`, heavy parsing/orchestration in new service modules, and `FrequencyService` gains only thin delegating methods — `frequency_service.py` (484 LOC) and `shaping.py` (574 LOC) are never grown.

**Tech Stack:** Python 3.12, FastMCP, Pydantic v2, `gql`/GraphQL against the gnomAD API, `uv` + Ruff + mypy, pytest (offline unit + `integration`-marked live). Pure carrier math is closed-form (no SciPy).

---

## Pre-Flight Reading

Read before starting (in order):

1. `AGENTS.md` — repo invariants, LOC cap, test boundaries.
2. `docs/superpowers/specs/2026-05-26-phase-c-new-tools-design.md` — the approved design for this plan.
3. `docs/superpowers/plans/2026-05-26-mcp-facade-polish.md` — the structural template these tasks mirror (task format, commit style).
4. `gnomad_link/mcp/tools/variants.py` — canonical `@mcp.tool` registration (decorator, `Annotated`/`Field`, inner `async def call()`, `run_mcp_tool`, `McpErrorContext`, `_meta.next_commands`).
5. `gnomad_link/mcp/annotations.py`, `gnomad_link/mcp/errors.py`, `gnomad_link/mcp/schema_relax.py` — `READ_ONLY_OPEN_WORLD`, `run_mcp_tool`/error codes, `relax_output_schema`.
6. `gnomad_link/mcp/shaping.py` — reusable helpers (`shape_variant_frequencies`, `shape_gene_variants`, `cap_region_span`, `_project_row`, `_to_restore_hint`, truncation-block shape). DO NOT add to this file (574/600).
7. `gnomad_link/mcp/resources.py` + `tests/unit/mcp/test_mcp_facade_surface.py` — the capabilities dict and the `test_capabilities_tools_match_facade_tools` parity gate.
8. `gnomad_link/services/frequency_service.py`, `gnomad_link/api/client.py`, `gnomad_link/graphql/query_loader.py`, `gnomad_link/graphql/query_builder.py` — service/client/query-loading surface.
9. `docs/gnomad_graphql/` — GraphQL reference (coverage, structural variants, pext/GTEx, ClinVar fields).

## Invariants (enforced in every task)

- Hand-authored facade pattern: one tool per `@mcp.tool` inside a `register_<area>_tools` function; new module wired by ONE import + ONE call line in `gnomad_link/mcp/tools/__init__.py` (`facade.py` untouched).
- Every `output_schema` wrapped in `relax_output_schema(...)`. `annotations=READ_ONLY_OPEN_WORLD`, `tags={...}`, a token-cost hint and an examples-bearing docstring beginning `Use this when …`.
- Every tool returns `dict[str, Any]` via `await run_mcp_tool(name, call, context=McpErrorContext(...))` so structured error envelopes survive SDK validation; the `name` string matches the decorator `name` and `McpErrorContext(tool_name=...)`.
- `_meta` carries `unsafe_for_clinical_use` + `gnomad_release` (injected by `run_mcp_tool`'s `_BASE_META` — never re-added) plus the tool's `next_commands` (≤3, no self-reference) merged in the `call()` closure.
- Research-use safety preserved; no clinical-decision-support framing.
- 600-LOC hard cap per module (`make lint-loc`). New shaping → dedicated `*_shaping.py`; new orchestration → new `services/*.py`; `shaping.py`/`frequency_service.py` never grown. No `.loc-allowlist` raises.
- No widening of Ruff/mypy ignore lists.
- TDD: every task starts with a failing test (real code), runs it expecting failure, implements minimally, re-runs to pass, then commits. Each task ends with `make ci-local` (PASS) before its commit.
- Unit tests offline under `tests/unit/` (services/client mocked); any live-gnomAD test `@pytest.mark.integration` under `tests/integration/`.
- Capabilities parity: in the SAME task that registers a tool, append it to `resources.py` (`tools`, `token_cost_hints` ≤80 chars, `tool_categories`) AND to `EXPECTED_TOOLS` in `tests/unit/mcp/test_mcp_facade_surface.py`.
- Atomic commits per task: `feat(mcp): …` / `refactor(mcp): …` / `chore(mcp): …`.

## Final Tool Surface (21 tools after Phase C)

| # | Tool | Category | Status |
|---|------|----------|--------|
| 1 | `get_server_capabilities` | metadata | existing |
| 2 | `get_gnomad_diagnostics` | metadata/diagnostics | existing |
| 3 | `get_variant_frequencies` | variant | existing |
| 4 | `get_variant_details` | variant | existing |
| 5 | `get_gene_details` | gene | existing |
| 6 | `get_gene_variants` | gene | existing |
| 7 | `get_clinvar_variant_details` | clinical | existing |
| 8 | `get_clinvar_meta` | clinical | existing (deprecated) |
| 9 | `liftover_variant` | coordinates | existing |
| 10 | `get_structural_variant` | variant | existing |
| 11 | `get_mitochondrial_variant` | variant | existing |
| 12 | `get_region` | coordinates | existing |
| 13 | `get_transcript_details` | gene | existing |
| 14 | `search_genes` | gene/search | existing |
| 15 | `resolve_variant_id` | search | existing |
| 16 | `search_variants` | search | existing (deprecated alias) |
| 17 | **`compute_carrier_frequency`** | variant | **NEW (C3)** |
| 18 | **`compare_variant_across_datasets`** | variant | **NEW (C2)** |
| 19 | **`get_gene_summary`** | gene | **NEW (C4)** |
| 20 | **`get_coverage`** | coordinates | **NEW (C1)** |
| 21 | **`search_structural_variants`** | variant/search | **NEW (C5)** |

## Execution order (recommended)

Lowest-risk first, per the design tiering: **C3 → C2 → C4 → C5 → C1**. C3/C2 are pure composition (no new GraphQL); C4 extends the gene query; C5/C1 add new query + service surface. Sections below are numbered by tool identity (C1…C5), not execution order — follow the sequence above.

## Shared-file edits are cumulative (read before executing)

Five tasks touch the same three files — `gnomad_link/mcp/tools/__init__.py`, `gnomad_link/mcp/resources.py` (`tools` list + `token_cost_hints` + `tool_categories`), and `EXPECTED_TOOLS` in `tests/unit/mcp/test_mcp_facade_surface.py`. These are independent **appends**; apply each against the current working-tree state (which already contains prior tasks' additions), NOT against the pristine snippet shown in each section. No two tasks target the same anchor line, so there is no merge conflict — just add cumulatively.

## Consistency review applied

These sections were drafted in parallel and then cross-checked by an adversarial consistency pass. Four defects it found are already corrected here: the C1 build-mismatch test now uses a chr1 coordinate that genuinely infers GRCh37; the C2 all-datasets-missing test raises `GnomadApiError` (an upstream error) rather than `DataNotFoundError` (partial-success); C4 fetches GTEx via a dedicated `transcript_gtex.graphql` + `get_transcript_gtex` client method (the existing transcript query selects no GTEx); and C2's `compute_carrier_frequency` next-command now passes the required `inheritance` argument.

---

## Phase C1: get_coverage — expose gnomAD exome/genome read-depth coverage for gene, region, and variant scopes

This phase adds a NEW MCP tool `get_coverage` backed by a NEW GraphQL surface (gnomAD `coverage` field), a NEW Pydantic model module, a NEW service module, and a NEW shaping module. It is the heaviest payload in the suite (per-position coverage bins), so compact mode trims each bin to a 4-field keep-set, caps bins per source, and computes a `{mean_coverage, fraction_over_20}` summary from the FULL bins before capping. Exactly one of `gene_symbol | gene_id | region | variant_id` is required. Region requests reuse the existing 100kb span cap and build-mismatch detection.

**Files**

- Create: `gnomad_link/graphql/queries/common/coverage.graphql` (3 operations: `gene_coverage`, `region_coverage`, `variant_coverage`)
- Create: `gnomad_link/models/coverage_models.py` (`CoverageBin`, `FeatureCoverage`, `Coverage`)
- Modify: `gnomad_link/models/__init__.py` (export the new models)
- Modify: `gnomad_link/graphql/query_builder.py` (no-op `coverage` variable handling — verify pass-through; only edit if needed)
- Modify: `gnomad_link/api/client.py` (3 client methods: `get_gene_coverage`, `get_region_coverage`, `get_variant_coverage`)
- Create: `gnomad_link/services/coverage_service.py` (`CoverageService`)
- Modify: `gnomad_link/services/__init__.py` (export `CoverageService`)
- Modify: `gnomad_link/services/frequency_service.py` (THIN `get_coverage` delegating method — a few lines only; file is at 484 LOC and must not balloon)
- Create: `gnomad_link/mcp/coverage_shaping.py` (`shape_coverage_payload` + keep-set + bin cap + summary-from-full)
- Create: `gnomad_link/mcp/tools/coverage.py` (`register_coverage_tools`)
- Modify: `gnomad_link/mcp/tools/__init__.py` (one import + one call line)
- Modify: `gnomad_link/mcp/resources.py` (append `get_coverage` to `tools`, `token_cost_hints`, `tool_categories`)
- Test: `tests/unit/services/test_coverage_service.py` (service unit test, mock client)
- Test: `tests/unit/graphql/test_coverage_query_loads.py` (query loads + has 3 ops)
- Test: `tests/unit/mcp/test_coverage_shaping.py` (shaping unit tests)
- Test: `tests/unit/mcp/test_coverage_tool.py` (tool dispatch / region cap / build check)
- Modify: `tests/unit/mcp/test_mcp_facade_surface.py` (add `get_coverage` to `EXPECTED_TOOLS`)

---

### Task C1.1: GraphQL coverage ops + coverage models + client methods + CoverageService

**Files:**
- Create: `gnomad_link/graphql/queries/common/coverage.graphql`
- Create: `gnomad_link/models/coverage_models.py`
- Modify: `gnomad_link/models/__init__.py`
- Modify: `gnomad_link/api/client.py`
- Create: `gnomad_link/services/coverage_service.py`
- Modify: `gnomad_link/services/__init__.py`
- Modify: `gnomad_link/services/frequency_service.py`
- Create: `tests/unit/graphql/test_coverage_query_loads.py`
- Create: `tests/unit/services/test_coverage_service.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/graphql/test_coverage_query_loads.py`:

```python
from __future__ import annotations

from gnomad_link.graphql.query_loader import QueryLoader


def test_coverage_query_file_loads_for_v4() -> None:
    loader = QueryLoader()
    doc = loader.load_query("coverage", "v4")
    assert "coverage" in doc


def test_coverage_query_defines_three_named_operations() -> None:
    loader = QueryLoader()
    doc = loader.load_query("coverage", "v4")
    assert "query gene_coverage(" in doc
    assert "query region_coverage(" in doc
    assert "query variant_coverage(" in doc


def test_region_coverage_requires_dataset_argument() -> None:
    loader = QueryLoader()
    doc = loader.load_query("coverage", "v4")
    # region.coverage takes a non-null DatasetId; gene/variant accept the nullable form.
    assert "$dataset: DatasetId!" in doc
```

Create `tests/unit/services/test_coverage_service.py`:

```python
from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.services.coverage_service import CoverageService


class _StubClient:
    def __init__(self) -> None:
        self.gene_calls: list[tuple[Any, ...]] = []
        self.region_calls: list[tuple[Any, ...]] = []
        self.variant_calls: list[tuple[Any, ...]] = []

    async def get_gene_coverage(
        self,
        *,
        gene_id: str | None,
        gene_symbol: str | None,
        reference_genome: str,
        dataset: str,
    ) -> dict[str, Any]:
        self.gene_calls.append((gene_id, gene_symbol, reference_genome, dataset))
        return {
            "gene": {
                "gene_id": gene_id or "ENSG00000169174",
                "symbol": gene_symbol or "PCSK9",
                "coverage": {
                    "exome": [{"pos": 100, "mean": 31.2, "median": 30, "over_20": 0.99, "over_30": 0.81}],
                    "genome": [{"pos": 100, "mean": 28.0, "median": 28, "over_20": 0.97, "over_30": 0.6}],
                },
            }
        }

    async def get_region_coverage(
        self,
        *,
        chrom: str,
        start: int,
        stop: int,
        reference_genome: str,
        dataset: str,
    ) -> dict[str, Any]:
        self.region_calls.append((chrom, start, stop, reference_genome, dataset))
        return {
            "region": {
                "chrom": chrom,
                "start": start,
                "stop": stop,
                "coverage": {
                    "exome": [{"pos": start, "mean": 30.0, "median": 30, "over_20": 0.98, "over_30": 0.7}],
                    "genome": [],
                },
            }
        }

    async def get_variant_coverage(
        self, *, variant_id: str, dataset: str
    ) -> dict[str, Any]:
        self.variant_calls.append((variant_id, dataset))
        return {
            "variant": {
                "variant_id": variant_id,
                "coverage": {
                    "exome": {"mean": 31.0, "median": 31, "over_20": 0.99, "over_30": 0.82},
                    "genome": {"mean": 27.0, "median": 27, "over_20": 0.95, "over_30": 0.55},
                },
            }
        }


@pytest.mark.asyncio
async def test_get_gene_coverage_maps_reference_genome_from_dataset() -> None:
    client = _StubClient()
    service = CoverageService(client=client)

    raw = await service.get_gene_coverage(
        gene_id=None, gene_symbol="PCSK9", dataset="gnomad_r4"
    )

    assert client.gene_calls == [(None, "PCSK9", "GRCh38", "gnomad_r4")]
    assert raw["gene"]["coverage"]["exome"][0]["mean"] == 31.2


@pytest.mark.asyncio
async def test_get_gene_coverage_uses_grch37_for_r2_1() -> None:
    client = _StubClient()
    service = CoverageService(client=client)

    await service.get_gene_coverage(
        gene_id="ENSG00000169174", gene_symbol=None, dataset="gnomad_r2_1"
    )

    assert client.gene_calls == [("ENSG00000169174", None, "GRCh37", "gnomad_r2_1")]


@pytest.mark.asyncio
async def test_get_region_coverage_passes_reference_genome_and_dataset() -> None:
    client = _StubClient()
    service = CoverageService(client=client)

    await service.get_region_coverage(
        chrom="1", start=55_039_447, stop=55_039_547, dataset="gnomad_r4"
    )

    assert client.region_calls == [("1", 55_039_447, 55_039_547, "GRCh38", "gnomad_r4")]


@pytest.mark.asyncio
async def test_get_variant_coverage_passes_dataset_only() -> None:
    client = _StubClient()
    service = CoverageService(client=client)

    raw = await service.get_variant_coverage(
        variant_id="1-55039447-A-G", dataset="gnomad_r4"
    )

    assert client.variant_calls == [("1-55039447-A-G", "gnomad_r4")]
    assert raw["variant"]["coverage"]["exome"]["mean"] == 31.0
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `uv run pytest tests/unit/graphql/test_coverage_query_loads.py tests/unit/services/test_coverage_service.py -q`
Expected: FAIL (`FileNotFoundError` for the query; `ModuleNotFoundError: No module named 'gnomad_link.services.coverage_service'`).

- [ ] **Step 3: Add the GraphQL document**

Create `gnomad_link/graphql/queries/common/coverage.graphql`. The gnomAD schema exposes `coverage(dataset: DatasetId)` on `gene` and `variant`, and `coverage(dataset: DatasetId!)` on `region` (non-null there). `gene`/`region` require `reference_genome: ReferenceGenomeId!`; `variant` takes `(variantId, dataset)`. Variant coverage is scalar (no `pos`, no bins).

```graphql
query gene_coverage(
    $gene_id: String
    $gene_symbol: String
    $reference_genome: ReferenceGenomeId!
    $dataset: DatasetId
) {
    gene(gene_id: $gene_id, gene_symbol: $gene_symbol, reference_genome: $reference_genome) {
        gene_id
        symbol
        coverage(dataset: $dataset) {
            exome {
                pos
                mean
                median
                over_1
                over_5
                over_10
                over_15
                over_20
                over_25
                over_30
                over_50
                over_100
            }
            genome {
                pos
                mean
                median
                over_1
                over_5
                over_10
                over_15
                over_20
                over_25
                over_30
                over_50
                over_100
            }
        }
    }
}

query region_coverage(
    $chrom: String!
    $start: Int!
    $stop: Int!
    $reference_genome: ReferenceGenomeId!
    $dataset: DatasetId!
) {
    region(chrom: $chrom, start: $start, stop: $stop, reference_genome: $reference_genome) {
        chrom
        start
        stop
        coverage(dataset: $dataset) {
            exome {
                pos
                mean
                median
                over_1
                over_5
                over_10
                over_15
                over_20
                over_25
                over_30
                over_50
                over_100
            }
            genome {
                pos
                mean
                median
                over_1
                over_5
                over_10
                over_15
                over_20
                over_25
                over_30
                over_50
                over_100
            }
        }
    }
}

query variant_coverage($variantId: String!, $dataset: DatasetId!) {
    variant(variantId: $variantId, dataset: $dataset) {
        variant_id
        coverage {
            exome {
                mean
                median
                over_20
                over_30
            }
            genome {
                mean
                median
                over_20
                over_30
            }
        }
    }
}
```

Note: `load_query("coverage", "v4")` falls back to `common/` (no `v4/coverage.graphql`), per `QueryLoader.load_query`. The document holds three named operations; the client selects one by `operationName` (Step 6).

- [ ] **Step 4: Add the coverage models**

Create `gnomad_link/models/coverage_models.py`:

```python
"""Pydantic models for gnomAD read-depth coverage (gene, region, variant)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CoverageBin(BaseModel):
    """A single per-position coverage bin (gene/region scope)."""

    pos: int
    mean: float | None = None
    median: float | None = None
    over_1: float | None = None
    over_5: float | None = None
    over_10: float | None = None
    over_15: float | None = None
    over_20: float | None = None
    over_25: float | None = None
    over_30: float | None = None
    over_50: float | None = None
    over_100: float | None = None

    model_config = ConfigDict(extra="allow")


class FeatureCoverage(BaseModel):
    """Coverage for a gene or region: per-position exome/genome bins."""

    exome: list[CoverageBin] = Field(default_factory=list)
    genome: list[CoverageBin] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class Coverage(BaseModel):
    """Scalar coverage for a single variant (no bins, no pos)."""

    mean: float | None = None
    median: float | None = None
    over_20: float | None = None
    over_30: float | None = None

    model_config = ConfigDict(extra="allow")
```

In `gnomad_link/models/__init__.py`, add the import after the region import block and extend `__all__`:

```python
from .coverage_models import Coverage, CoverageBin, FeatureCoverage
```

```python
    # Coverage models
    "Coverage",
    "CoverageBin",
    "FeatureCoverage",
```

- [ ] **Step 5: Add the three client methods**

In `gnomad_link/api/client.py`, append these methods to `UnifiedGnomadClient` (after `get_liftover`). The `coverage` query_type is unknown to `QueryBuilder.process_variables`, so variables pass through unchanged — the methods supply `reference_genome` explicitly (mirroring the gene/region pattern) and use `operation_name` to pick the right named operation in the multi-op document.

```python
    async def get_gene_coverage(
        self,
        *,
        gene_id: str | None,
        gene_symbol: str | None,
        reference_genome: str,
        dataset: str,
    ) -> dict[str, Any]:
        """Get per-position exome/genome coverage bins for a gene."""
        version = QueryBuilder.get_version_for_dataset(dataset)
        variables: dict[str, Any] = {
            "reference_genome": reference_genome,
            "dataset": dataset,
        }
        if gene_id:
            variables["gene_id"] = gene_id
        if gene_symbol:
            variables["gene_symbol"] = gene_symbol
        return await self.execute_query(
            "coverage", variables, version, operation_name="gene_coverage"
        )

    async def get_region_coverage(
        self,
        *,
        chrom: str,
        start: int,
        stop: int,
        reference_genome: str,
        dataset: str,
    ) -> dict[str, Any]:
        """Get per-position exome/genome coverage bins for a region."""
        version = QueryBuilder.get_version_for_dataset(dataset)
        variables: dict[str, Any] = {
            "chrom": chrom,
            "start": start,
            "stop": stop,
            "reference_genome": reference_genome,
            "dataset": dataset,
        }
        return await self.execute_query(
            "coverage", variables, version, operation_name="region_coverage"
        )

    async def get_variant_coverage(
        self, *, variant_id: str, dataset: str
    ) -> dict[str, Any]:
        """Get scalar exome/genome coverage for a single variant."""
        version = QueryBuilder.get_version_for_dataset(dataset)
        variables: dict[str, Any] = {"variantId": variant_id, "dataset": dataset}
        return await self.execute_query(
            "coverage", variables, version, operation_name="variant_coverage"
        )
```

`execute_query` does not currently accept an `operation_name`. Add the parameter in `gnomad_link/api/base_client.py` `execute_query` (default `None`, threaded into `execute_async` and skipping the `None`-data guard for multi-op docs):

In the signature:

```python
    async def execute_query(
        self,
        query_name: str,
        variables: dict[str, Any],
        version: str = "v4",
        operation_name: str | None = None,
    ) -> dict[str, Any]:
```

In the body, replace the execute + data-guard region with:

```python
            query_doc = gql(query_string)
            if operation_name is not None:
                result = await self._client.execute_async(
                    query_doc,
                    variable_values=processed_vars,
                    operation_name=operation_name,
                )
            else:
                result = await self._client.execute_async(
                    query_doc, variable_values=processed_vars
                )

            # Check if data was found (single-op queries are keyed by query_name).
            if (
                operation_name is None
                and query_name in result
                and result[query_name] is None
            ):
                raise DataNotFoundError(
                    f"No data found for {query_name} with parameters: {processed_vars}"
                )
```

The CoverageService (Step 6) raises `DataNotFoundError` for empty coverage so the `not_found` envelope still fires for multi-op coverage queries.

- [ ] **Step 6: Add CoverageService**

Create `gnomad_link/services/coverage_service.py`:

```python
"""Service layer for gnomAD read-depth coverage (gene, region, variant scopes)."""

from __future__ import annotations

from typing import Any

from gnomad_link.api.base_client import DataNotFoundError
from gnomad_link.api.client import UnifiedGnomadClient


def _reference_genome_for(dataset: str) -> str:
    """gnomad_r2_1 is GRCh37; r3/r4 are GRCh38."""
    return "GRCh37" if dataset == "gnomad_r2_1" else "GRCh38"


class CoverageService:
    """Fetch coverage payloads from the unified client.

    Thin orchestration: maps dataset -> reference build, calls the matching
    client method, and raises DataNotFoundError when the feature is absent so
    callers get the structured not_found envelope.
    """

    def __init__(self, client: UnifiedGnomadClient | None = None) -> None:
        self.client = client or UnifiedGnomadClient()

    async def get_gene_coverage(
        self, *, gene_id: str | None, gene_symbol: str | None, dataset: str
    ) -> dict[str, Any]:
        raw = await self.client.get_gene_coverage(
            gene_id=gene_id,
            gene_symbol=gene_symbol,
            reference_genome=_reference_genome_for(dataset),
            dataset=dataset,
        )
        if not (raw.get("gene") or {}).get("coverage"):
            raise DataNotFoundError(
                f"No coverage for gene {gene_id or gene_symbol} in {dataset}"
            )
        return raw

    async def get_region_coverage(
        self, *, chrom: str, start: int, stop: int, dataset: str
    ) -> dict[str, Any]:
        raw = await self.client.get_region_coverage(
            chrom=chrom,
            start=start,
            stop=stop,
            reference_genome=_reference_genome_for(dataset),
            dataset=dataset,
        )
        if not (raw.get("region") or {}).get("coverage"):
            raise DataNotFoundError(
                f"No coverage for region {chrom}-{start}-{stop} in {dataset}"
            )
        return raw

    async def get_variant_coverage(
        self, *, variant_id: str, dataset: str
    ) -> dict[str, Any]:
        raw = await self.client.get_variant_coverage(
            variant_id=variant_id, dataset=dataset
        )
        if not (raw.get("variant") or {}).get("coverage"):
            raise DataNotFoundError(
                f"No coverage for variant {variant_id} in {dataset}"
            )
        return raw
```

In `gnomad_link/services/__init__.py`, export `CoverageService` (mirror the existing `FrequencyService` export — add the import and the `__all__` entry).

- [ ] **Step 7: Add the THIN FrequencyService delegate**

The tool calls `service.get_coverage(...)` to keep the single-service call site convention. In `gnomad_link/services/frequency_service.py`, add ONE small method on `FrequencyService` (lazily constructing a `CoverageService` over the same client — keep it a few lines so the 484-LOC file does not balloon). Place the import at the top of the file with the other service imports is NOT possible (would be circular within the package `__init__`); import inside the method instead:

```python
    async def get_coverage(
        self,
        *,
        scope: str,
        dataset: str,
        gene_id: str | None = None,
        gene_symbol: str | None = None,
        chrom: str | None = None,
        start: int | None = None,
        stop: int | None = None,
        variant_id: str | None = None,
    ) -> dict[str, Any]:
        """Delegate to CoverageService; keeps tool call sites on a single service."""
        from gnomad_link.services.coverage_service import CoverageService

        coverage = CoverageService(client=self.client)
        if scope == "gene":
            return await coverage.get_gene_coverage(
                gene_id=gene_id, gene_symbol=gene_symbol, dataset=dataset
            )
        if scope == "region":
            assert chrom is not None and start is not None and stop is not None
            return await coverage.get_region_coverage(
                chrom=chrom, start=start, stop=stop, dataset=dataset
            )
        return await coverage.get_variant_coverage(
            variant_id=variant_id or "", dataset=dataset
        )
```

- [ ] **Step 8: Run the focused tests**

Run: `uv run pytest tests/unit/graphql/test_coverage_query_loads.py tests/unit/services/test_coverage_service.py -q`
Expected: PASS (7 tests).

- [ ] **Step 9: Run the full local CI gate**

Run: `make ci-local`
Expected: PASS (format, lint, lint-loc, typecheck, tests all green; every new module well under 600 LOC).

- [ ] **Step 10: Commit**

```
git add gnomad_link/graphql/queries/common/coverage.graphql gnomad_link/models/coverage_models.py gnomad_link/models/__init__.py gnomad_link/api/client.py gnomad_link/api/base_client.py gnomad_link/services/coverage_service.py gnomad_link/services/__init__.py gnomad_link/services/frequency_service.py tests/unit/graphql/test_coverage_query_loads.py tests/unit/services/test_coverage_service.py
git commit -m "feat(mcp): add coverage GraphQL ops, models, client methods, and CoverageService"
```

---

### Task C1.2: coverage_shaping — keep-set, per-source bin cap, summary computed from full bins

**Files:**
- Create: `gnomad_link/mcp/coverage_shaping.py`
- Create: `tests/unit/mcp/test_coverage_shaping.py`

`shape_coverage_payload` projects a service payload into the success shape:
`{scope, identity, dataset, exome, genome}`. For `gene`/`region` scope `exome`/`genome` are `{bins:[...], summary:{mean_coverage, fraction_over_20}, truncated?}`; for `variant` scope they are scalar `{mean, median, over_20, over_30}`. Compact mode trims each bin to `mean, median, over_20, over_30` (plus `pos`). The summary is computed from the FULL bins BEFORE the cap, so it stays accurate even when bins are truncated. The truncated block uses the self-describing shape from `shaping.py` (`kind`, `dropped`, `to_disable`, `to_restore`). NEVER add to `shaping.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/mcp/test_coverage_shaping.py`:

```python
from __future__ import annotations

from typing import Any

from gnomad_link.mcp.coverage_shaping import shape_coverage_payload

_COMPACT_KEEP = {"pos", "mean", "median", "over_20", "over_30"}


def _bin(pos: int, mean: float, over_20: float) -> dict[str, Any]:
    return {
        "pos": pos,
        "mean": mean,
        "median": mean,
        "over_1": 1.0,
        "over_10": 0.99,
        "over_20": over_20,
        "over_30": over_20 - 0.1,
        "over_100": 0.0,
    }


def test_gene_scope_compact_trims_bins_to_keep_set() -> None:
    raw = {
        "gene": {
            "gene_id": "ENSG00000169174",
            "symbol": "PCSK9",
            "coverage": {
                "exome": [_bin(100, 30.0, 0.99)],
                "genome": [_bin(100, 25.0, 0.9)],
            },
        }
    }

    shaped = shape_coverage_payload(
        raw, scope="gene", dataset="gnomad_r4", response_mode="compact", max_bins=500
    )

    assert shaped["scope"] == "gene"
    assert shaped["identity"] == {"gene_id": "ENSG00000169174", "symbol": "PCSK9"}
    assert shaped["dataset"] == "gnomad_r4"
    exome_bin = shaped["exome"]["bins"][0]
    assert set(exome_bin) == _COMPACT_KEEP
    assert "over_100" not in exome_bin


def test_gene_scope_full_keeps_all_bin_fields() -> None:
    raw = {
        "gene": {
            "gene_id": "ENSG1",
            "symbol": "G",
            "coverage": {"exome": [_bin(100, 30.0, 0.99)], "genome": []},
        }
    }

    shaped = shape_coverage_payload(
        raw, scope="gene", dataset="gnomad_r4", response_mode="full", max_bins=500
    )

    assert "over_100" in shaped["exome"]["bins"][0]


def test_summary_computed_from_full_bins_before_cap() -> None:
    # 4 bins; cap to 2. Summary must reflect all 4.
    exome = [_bin(p, mean=float(p), over_20=1.0 if p <= 2 else 0.0) for p in (1, 2, 3, 4)]
    raw = {
        "gene": {
            "gene_id": "ENSG1",
            "symbol": "G",
            "coverage": {"exome": exome, "genome": []},
        }
    }

    shaped = shape_coverage_payload(
        raw, scope="gene", dataset="gnomad_r4", response_mode="compact", max_bins=2
    )

    summary = shaped["exome"]["summary"]
    assert summary["mean_coverage"] == 2.5  # (1+2+3+4)/4
    assert summary["fraction_over_20"] == 0.5  # 2 of 4 bins over_20 == 1.0
    assert len(shaped["exome"]["bins"]) == 2


def test_bin_cap_emits_self_describing_truncated_block() -> None:
    exome = [_bin(p, 30.0, 0.99) for p in range(10)]
    raw = {
        "gene": {
            "gene_id": "ENSG1",
            "symbol": "G",
            "coverage": {"exome": exome, "genome": []},
        }
    }

    shaped = shape_coverage_payload(
        raw, scope="gene", dataset="gnomad_r4", response_mode="compact", max_bins=4
    )

    trunc = shaped["exome"]["truncated"]
    assert trunc["kind"] == "coverage_bins"
    assert trunc["dropped"] == 6
    assert "max_bins" in trunc["to_disable"]
    assert "max_bins" in trunc["to_restore"]


def test_no_truncated_block_when_under_cap() -> None:
    raw = {
        "gene": {
            "gene_id": "ENSG1",
            "symbol": "G",
            "coverage": {"exome": [_bin(1, 30.0, 0.99)], "genome": []},
        }
    }

    shaped = shape_coverage_payload(
        raw, scope="gene", dataset="gnomad_r4", response_mode="compact", max_bins=500
    )

    assert "truncated" not in shaped["exome"]


def test_region_scope_identity_is_chrom_start_stop() -> None:
    raw = {
        "region": {
            "chrom": "1",
            "start": 100,
            "stop": 200,
            "coverage": {"exome": [_bin(100, 30.0, 0.99)], "genome": []},
        }
    }

    shaped = shape_coverage_payload(
        raw, scope="region", dataset="gnomad_r4", response_mode="compact", max_bins=500
    )

    assert shaped["scope"] == "region"
    assert shaped["identity"] == {"chrom": "1", "start": 100, "stop": 200}


def test_variant_scope_is_scalar_no_bins() -> None:
    raw = {
        "variant": {
            "variant_id": "1-55039447-A-G",
            "coverage": {
                "exome": {"mean": 31.0, "median": 31, "over_20": 0.99, "over_30": 0.82},
                "genome": {"mean": 27.0, "median": 27, "over_20": 0.95, "over_30": 0.55},
            },
        }
    }

    shaped = shape_coverage_payload(
        raw, scope="variant", dataset="gnomad_r4", response_mode="compact", max_bins=500
    )

    assert shaped["scope"] == "variant"
    assert shaped["identity"] == {"variant_id": "1-55039447-A-G"}
    assert shaped["exome"] == {"mean": 31.0, "median": 31, "over_20": 0.99, "over_30": 0.82}
    assert "bins" not in shaped["exome"]
    assert shaped["genome"]["mean"] == 27.0
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `uv run pytest tests/unit/mcp/test_coverage_shaping.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'gnomad_link.mcp.coverage_shaping'`).

- [ ] **Step 3: Implement coverage_shaping**

Create `gnomad_link/mcp/coverage_shaping.py`:

```python
"""Shape gnomAD coverage payloads into compact MCP responses.

Per-position coverage bins are the heaviest payload in the suite. Compact mode
trims each bin to a 4-field keep-set (plus pos), caps bins per source, and emits
a self-describing `truncated` block. The {mean_coverage, fraction_over_20}
summary is computed from the FULL bins BEFORE the cap so it stays accurate even
when the returned bins are truncated. Lives in its own module to keep
gnomad_link/mcp/shaping.py from growing.
"""

from __future__ import annotations

from typing import Any

# Compact keep-set per bin (pos always retained for gene/region bins).
_COMPACT_BIN_KEEP = {"pos", "mean", "median", "over_20", "over_30"}
# Scalar (variant-scope) coverage keep-set.
_SCALAR_KEEP = {"mean", "median", "over_20", "over_30"}


def _bin_summary(bins: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute {mean_coverage, fraction_over_20} from the FULL bin list."""
    means = [b["mean"] for b in bins if b.get("mean") is not None]
    over_20 = [b["over_20"] for b in bins if b.get("over_20") is not None]
    return {
        "mean_coverage": round(sum(means) / len(means), 4) if means else None,
        "fraction_over_20": round(sum(over_20) / len(over_20), 4) if over_20 else None,
    }


def _project_bin(b: dict[str, Any], *, compact: bool) -> dict[str, Any]:
    if not compact:
        return b
    return {k: v for k, v in b.items() if k in _COMPACT_BIN_KEEP}


def _shape_feature_source(
    bins: list[dict[str, Any]] | None, *, compact: bool, max_bins: int
) -> dict[str, Any]:
    """Shape one gene/region source (exome or genome) into bins+summary+truncated."""
    bins = bins or []
    summary = _bin_summary(bins)  # from FULL bins, before cap
    projected = [_project_bin(b, compact=compact) for b in bins]
    out: dict[str, Any] = {"bins": projected[:max_bins], "summary": summary}
    if len(projected) > max_bins:
        out["bins"] = projected[:max_bins]
        out["truncated"] = {
            "kind": "coverage_bins",
            "dropped": len(projected) - max_bins,
            "to_disable": "raise max_bins (the summary already reflects all bins)",
            "to_restore": f"max_bins={len(projected)}",
        }
    return out


def _shape_scalar_source(source: dict[str, Any] | None, *, compact: bool) -> dict[str, Any] | None:
    if source is None:
        return None
    if not compact:
        return source
    return {k: v for k, v in source.items() if k in _SCALAR_KEEP}


def shape_coverage_payload(
    raw: dict[str, Any],
    *,
    scope: str,
    dataset: str,
    response_mode: str,
    max_bins: int,
) -> dict[str, Any]:
    """Project a CoverageService payload into the get_coverage success shape."""
    compact = response_mode == "compact"

    if scope == "variant":
        feature = raw.get("variant") or {}
        coverage = feature.get("coverage") or {}
        return {
            "scope": "variant",
            "identity": {"variant_id": feature.get("variant_id")},
            "dataset": dataset,
            "exome": _shape_scalar_source(coverage.get("exome"), compact=compact),
            "genome": _shape_scalar_source(coverage.get("genome"), compact=compact),
        }

    if scope == "region":
        feature = raw.get("region") or {}
        identity = {
            "chrom": feature.get("chrom"),
            "start": feature.get("start"),
            "stop": feature.get("stop"),
        }
    else:  # gene
        feature = raw.get("gene") or {}
        identity = {"gene_id": feature.get("gene_id"), "symbol": feature.get("symbol")}

    coverage = feature.get("coverage") or {}
    return {
        "scope": scope,
        "identity": identity,
        "dataset": dataset,
        "exome": _shape_feature_source(
            coverage.get("exome"), compact=compact, max_bins=max_bins
        ),
        "genome": _shape_feature_source(
            coverage.get("genome"), compact=compact, max_bins=max_bins
        ),
    }
```

- [ ] **Step 4: Run the focused tests**

Run: `uv run pytest tests/unit/mcp/test_coverage_shaping.py -q`
Expected: PASS (8 tests).

- [ ] **Step 5: Run the full local CI gate**

Run: `make ci-local`
Expected: PASS.

- [ ] **Step 6: Commit**

```
git add gnomad_link/mcp/coverage_shaping.py tests/unit/mcp/test_coverage_shaping.py
git commit -m "feat(mcp): add coverage_shaping with compact keep-set, bin cap, and full-bin summary"
```

---

### Task C1.3: get_coverage tool — scope dispatch, region cap + build check, capabilities/parity sync

**Files:**
- Create: `gnomad_link/mcp/tools/coverage.py`
- Modify: `gnomad_link/mcp/tools/__init__.py`
- Modify: `gnomad_link/mcp/resources.py`
- Modify: `tests/unit/mcp/test_mcp_facade_surface.py`
- Create: `tests/unit/mcp/test_coverage_tool.py`

The tool requires exactly one of `gene_symbol | gene_id | region | variant_id`. It derives `scope` from which argument is set, raises `ValueError` (→ `validation_failed`) when zero or more than one is provided. Region scope reuses `cap_region_span(max_bp=100_000)` and `detect_region_mismatch` (→ `BuildMismatchError` → `build_mismatch`). Variant scope reuses `detect_variant_id_mismatch`. `next_commands` route to `get_variant_frequencies` (variant scope), `get_region`, `get_gene_details` — max 3, no self-reference.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/mcp/test_coverage_tool.py`:

```python
from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.mcp.facade import create_gnomad_mcp


class _StubCoverageService:
    """Captures the get_coverage kwargs the tool passes."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def get_coverage(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        scope = kwargs["scope"]
        if scope == "gene":
            return {
                "gene": {
                    "gene_id": "ENSG00000169174",
                    "symbol": "PCSK9",
                    "coverage": {
                        "exome": [
                            {"pos": 100, "mean": 31.0, "median": 31, "over_20": 0.99, "over_30": 0.8}
                        ],
                        "genome": [],
                    },
                }
            }
        if scope == "region":
            return {
                "region": {
                    "chrom": kwargs["chrom"],
                    "start": kwargs["start"],
                    "stop": kwargs["stop"],
                    "coverage": {
                        "exome": [
                            {"pos": kwargs["start"], "mean": 30.0, "median": 30, "over_20": 0.98, "over_30": 0.7}
                        ],
                        "genome": [],
                    },
                }
            }
        return {
            "variant": {
                "variant_id": kwargs["variant_id"],
                "coverage": {
                    "exome": {"mean": 31.0, "median": 31, "over_20": 0.99, "over_30": 0.82},
                    "genome": {"mean": 27.0, "median": 27, "over_20": 0.95, "over_30": 0.55},
                },
            }
        }


@pytest.mark.asyncio
async def test_get_coverage_gene_scope_by_symbol() -> None:
    service = _StubCoverageService()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    result = await mcp.call_tool("get_coverage", {"gene_symbol": "PCSK9"})
    payload = result.structured_content or {}

    assert payload["scope"] == "gene"
    assert payload["identity"]["symbol"] == "PCSK9"
    assert service.calls[0]["scope"] == "gene"
    assert service.calls[0]["gene_symbol"] == "PCSK9"
    assert payload["exome"]["summary"]["mean_coverage"] == 31.0


@pytest.mark.asyncio
async def test_get_coverage_variant_scope_is_scalar_and_links_to_frequencies() -> None:
    service = _StubCoverageService()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    result = await mcp.call_tool(
        "get_coverage", {"variant_id": "1-55039447-A-G", "dataset": "gnomad_r4"}
    )
    payload = result.structured_content or {}

    assert payload["scope"] == "variant"
    assert "bins" not in payload["exome"]
    next_tools = [c["tool"] for c in payload["_meta"]["next_commands"]]
    assert "get_variant_frequencies" in next_tools
    assert "get_coverage" not in next_tools  # no self-reference


@pytest.mark.asyncio
async def test_get_coverage_region_scope_caps_span_at_100kb() -> None:
    service = _StubCoverageService()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    # 500kb span exceeds the 100kb cap.
    result = await mcp.call_tool("get_coverage", {"region": "1-55000000-55500000"})
    payload = result.structured_content or {}

    assert payload["scope"] == "region"
    # Span was clamped before the service call.
    assert service.calls[0]["stop"] - service.calls[0]["start"] == 100_000


@pytest.mark.asyncio
async def test_get_coverage_requires_exactly_one_scope_arg() -> None:
    service = _StubCoverageService()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    result = await mcp.call_tool("get_coverage", {})
    payload = result.structured_content or {}

    assert payload["success"] is False
    assert payload["error_code"] == "validation_failed"
    assert service.calls == []


@pytest.mark.asyncio
async def test_get_coverage_rejects_two_scope_args() -> None:
    service = _StubCoverageService()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    result = await mcp.call_tool(
        "get_coverage", {"gene_symbol": "PCSK9", "variant_id": "1-55039447-A-G"}
    )
    payload = result.structured_content or {}

    assert payload["error_code"] == "validation_failed"
    assert service.calls == []


@pytest.mark.asyncio
async def test_get_coverage_region_build_mismatch_against_r4() -> None:
    service = _StubCoverageService()
    mcp = create_gnomad_mcp(service_factory=lambda: service)

    # chr1 is longer on GRCh37 (249,250,621 bp) than GRCh38 (248,956,422 bp),
    # so pos ~248.99Mb is valid only on GRCh37 and infers a GRCh37 build.
    # Querying it against gnomad_r4 (GRCh38) must raise build_mismatch.
    result = await mcp.call_tool(
        "get_coverage", {"region": "1-248990000-248990100", "dataset": "gnomad_r4"}
    )
    payload = result.structured_content or {}

    assert payload["error_code"] == "build_mismatch"
    assert payload["fallback_tool"] == "liftover_variant"
    assert service.calls == []


@pytest.mark.asyncio
async def test_get_coverage_registered_and_advertised(fake_service_factory) -> None:
    from gnomad_link.mcp.resources import get_capabilities_resource

    mcp = create_gnomad_mcp(service_factory=fake_service_factory)
    names = {tool.name for tool in await mcp.list_tools()}
    assert "get_coverage" in names
    caps = get_capabilities_resource()
    assert "get_coverage" in caps["tools"]
    assert "get_coverage" in caps["token_cost_hints"]
    assert "get_coverage" in caps["tool_categories"]["coordinates"]
```

In `tests/unit/mcp/test_mcp_facade_surface.py`, add `"get_coverage"` to the `EXPECTED_TOOLS` set (so the `test_capabilities_tools_match_facade_tools` parity gate and the data-tool annotation/output-schema/description sweeps cover it):

```python
    "get_coverage",
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `uv run pytest tests/unit/mcp/test_coverage_tool.py tests/unit/mcp/test_mcp_facade_surface.py -q`
Expected: FAIL (`get_coverage` not registered; `EXPECTED_TOOLS` parity and `test_capabilities_tools_match_facade_tools` mismatch).

- [ ] **Step 3: Implement the tool**

Create `gnomad_link/mcp/tools/coverage.py`:

```python
"""Coverage tool: get_coverage (gene, region, variant read-depth)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.build_check import (
    detect_region_mismatch,
    detect_variant_id_mismatch,
)
from gnomad_link.mcp.coverage_shaping import shape_coverage_payload
from gnomad_link.mcp.errors import BuildMismatchError, McpErrorContext, run_mcp_tool
from gnomad_link.mcp.schema_relax import relax_output_schema
from gnomad_link.mcp.shaping import cap_region_span
from gnomad_link.services import FrequencyService

_AUTOSOMAL_VARIANT_ID_PATTERN = r"^([1-9]|1\d|2[0-2]|X|Y)-\d+-[ACGT]+-[ACGT]+$"
_GENE_ID_PATTERN = r"^ENSG\d{11}$"
_GENE_SYMBOL_PATTERN = r"^[A-Za-z0-9._-]{1,32}$"
_REGION_PATTERN = r"^(chr)?([1-9]|1[0-9]|2[0-2]|X|Y)-\d+-\d+$"

_COVERAGE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "scope": {"type": "string"},
        "identity": {"type": "object"},
        "dataset": {"type": "string"},
        "exome": {"type": ["object", "null"]},
        "genome": {"type": ["object", "null"]},
    },
    "required": ["scope", "dataset"],
    "additionalProperties": True,
}


def register_coverage_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="get_coverage",
        title="Get Read-Depth Coverage",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=relax_output_schema(_COVERAGE_OUTPUT_SCHEMA),
        tags={"coordinates"},
    )
    async def get_coverage(
        gene_symbol: Annotated[
            str | None,
            Field(
                default=None,
                description="HGNC gene symbol (e.g. PCSK9). One scope arg only.",
                pattern=_GENE_SYMBOL_PATTERN,
                examples=["PCSK9"],
            ),
        ] = None,
        gene_id: Annotated[
            str | None,
            Field(
                default=None,
                description="Ensembl gene ID (ENSG...). One scope arg only.",
                pattern=_GENE_ID_PATTERN,
                examples=["ENSG00000169174"],
            ),
        ] = None,
        region: Annotated[
            str | None,
            Field(
                default=None,
                description="chr-start-stop (e.g. 1-55039447-55064852). Span capped at 100kb. One scope arg only.",
                pattern=_REGION_PATTERN,
                examples=["1-55039447-55064852"],
            ),
        ] = None,
        variant_id: Annotated[
            str | None,
            Field(
                default=None,
                description="CHROM-POS-REF-ALT for scalar per-variant coverage. One scope arg only.",
                pattern=_AUTOSOMAL_VARIANT_ID_PATTERN,
                examples=["1-55039447-A-G"],
            ),
        ] = None,
        dataset: Annotated[
            Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"],
            Field(
                description="gnomad_r4 (GRCh38, default), gnomad_r3 (GRCh38), gnomad_r2_1 (GRCh37 legacy)",
                examples=["gnomad_r4"],
            ),
        ] = "gnomad_r4",
        response_mode: Annotated[
            Literal["compact", "full"],
            Field(description="compact trims each bin to pos/mean/median/over_20/over_30; full keeps all over_* thresholds."),
        ] = "compact",
        max_bins: Annotated[
            int,
            Field(ge=1, le=20_000, description="Cap on coverage bins per source (gene/region). Summary still reflects all bins."),
        ] = 2_000,
    ) -> dict[str, Any]:
        """Use this when a caller needs gnomAD read-depth coverage for a gene, region, or single variant. Provide exactly ONE of gene_symbol, gene_id, region, or variant_id. Gene/region return per-position bins plus a {mean_coverage, fraction_over_20} summary; variant returns scalar coverage. Compact mode trims each bin and caps bin count. Returns ~3-40kB compact (bin-count dependent), larger with response_mode='full'."""

        provided = [
            ("gene_symbol", gene_symbol),
            ("gene_id", gene_id),
            ("region", region),
            ("variant_id", variant_id),
        ]
        set_args = [name for name, value in provided if value]

        async def call() -> dict[str, Any]:
            if len(set_args) != 1:
                raise ValueError(
                    "Provide exactly one of gene_symbol, gene_id, region, or variant_id "
                    f"(got {len(set_args)}: {set_args})."
                )
            service = service_factory()

            if region is not None:
                chrom, start_s, stop_s = region.removeprefix("chr").split("-")
                start, stop = int(start_s), int(stop_s)
                if stop <= start:
                    raise ValueError("Region stop must be greater than start.")
                inferred = detect_region_mismatch(chrom, start, dataset)
                if inferred is not None:
                    raise BuildMismatchError(
                        variant_id=f"{chrom}-{start}-{stop}",
                        inferred_build=inferred,
                        dataset=dataset,
                    )
                adj_start, adj_stop, _capped = cap_region_span(chrom, start, stop)
                raw = await service.get_coverage(
                    scope="region",
                    dataset=dataset,
                    chrom=chrom,
                    start=adj_start,
                    stop=adj_stop,
                )
                scope = "region"
                next_commands = [
                    {"tool": "get_region", "arguments": {"region": region, "dataset": dataset}},
                ]
            elif variant_id is not None:
                inferred = detect_variant_id_mismatch(variant_id, dataset)
                if inferred is not None:
                    raise BuildMismatchError(
                        variant_id=variant_id, inferred_build=inferred, dataset=dataset
                    )
                raw = await service.get_coverage(
                    scope="variant", dataset=dataset, variant_id=variant_id
                )
                scope = "variant"
                next_commands = [
                    {
                        "tool": "get_variant_frequencies",
                        "arguments": {"variant_id": variant_id, "dataset": dataset},
                    },
                ]
            else:  # gene_symbol or gene_id
                raw = await service.get_coverage(
                    scope="gene",
                    dataset=dataset,
                    gene_id=gene_id,
                    gene_symbol=gene_symbol,
                )
                scope = "gene"
                gene_args: dict[str, Any] = {"dataset": dataset}
                if gene_symbol:
                    gene_args["gene_symbol"] = gene_symbol
                if gene_id:
                    gene_args["gene_id"] = gene_id
                next_commands = [
                    {"tool": "get_gene_details", "arguments": gene_args},
                ]

            shaped = shape_coverage_payload(
                raw,
                scope=scope,
                dataset=dataset,
                response_mode=response_mode,
                max_bins=max_bins,
            )
            existing_meta: dict[str, Any] = shaped.get("_meta") or {}
            existing_next: list[Any] = existing_meta.get("next_commands", [])
            shaped["_meta"] = {
                **existing_meta,
                "next_commands": [*existing_next, *next_commands],
            }
            return shaped

        return await run_mcp_tool(
            "get_coverage",
            call,
            context=McpErrorContext(
                tool_name="get_coverage",
                gene_id=gene_id,
                gene_symbol=gene_symbol,
                region=region,
                variant_id=variant_id,
                dataset=dataset,
            ),
        )
```

In `gnomad_link/mcp/tools/__init__.py`, add the import (alphabetical, after `coordinates`):

```python
from gnomad_link.mcp.tools.coverage import register_coverage_tools
```

and the call line inside `register_gnomad_tools` (after `register_coordinate_tools`):

```python
    register_coverage_tools(mcp, service_factory=service_factory)
```

- [ ] **Step 4: Sync capabilities resource**

In `gnomad_link/mcp/resources.py`, append `"get_coverage"` to the `tools` list (after `"get_region"`):

```python
            "get_coverage",
```

add the token-cost hint (≤80 chars) to `token_cost_hints`:

```python
            "get_coverage": "compact ~3-40kB (bin-count dependent), full larger",
```

and add `"get_coverage"` to the `coordinates` list under `tool_categories`:

```python
            "coordinates": [
                "liftover_variant",
                "get_region",
                "get_transcript_details",
                "get_coverage",
            ],
```

- [ ] **Step 5: Run the focused tests**

Run: `uv run pytest tests/unit/mcp/test_coverage_tool.py tests/unit/mcp/test_mcp_facade_surface.py -q`
Expected: PASS (8 coverage-tool tests plus the full facade-surface suite green, including `test_capabilities_tools_match_facade_tools` and `test_capabilities_resource_lists_token_cost_hints`).

- [ ] **Step 6: Run the full local CI gate**

Run: `make ci-local`
Expected: PASS (format, lint, lint-loc ≤600 LOC on every module, typecheck, full unit suite).

- [ ] **Step 7: Commit**

```
git add gnomad_link/mcp/tools/coverage.py gnomad_link/mcp/tools/__init__.py gnomad_link/mcp/resources.py tests/unit/mcp/test_coverage_tool.py tests/unit/mcp/test_mcp_facade_surface.py
git commit -m "feat(mcp): add get_coverage tool with gene/region/variant scope dispatch and capabilities sync"
```

---

## Phase C2: compare_variant_across_datasets — fan out one variant across gnomAD releases and surface per-population AF deltas

A pure-composition tool. No new GraphQL documents, client methods, or `FrequencyService` methods beyond what already exists (`get_variant_frequencies`, `liftover_variant`). One new shaping module aligns per-population AF across datasets and computes deltas, reusing the existing `shape_variant_frequencies` projection per dataset. One new tool module fans out across datasets with partial-success semantics and optional auto-liftover for the GRCh37 `gnomad_r2_1` dataset.

**Files:**
- Create: `gnomad_link/mcp/comparison_shaping.py` — align per-dataset frequency shapes and compute per-population deltas
- Create: `gnomad_link/mcp/tools/comparison.py` — `register_comparison_tools(mcp, *, service_factory)` with the `compare_variant_across_datasets` tool
- Modify: `gnomad_link/mcp/tools/__init__.py` — one import + one call line
- Modify: `gnomad_link/mcp/resources.py` — append the tool to `tools`, `token_cost_hints`, and `tool_categories`
- Test: `tests/unit/mcp/test_comparison_shaping.py` — pure shaping unit tests over fixture dicts
- Test: `tests/unit/mcp/test_mcp_facade_surface.py` — add the tool to `EXPECTED_TOOLS`
- Test: `tests/unit/mcp/test_compare_variant.py` — tool-level fan-out, partial success, and auto-liftover tests

---

### Task C2.1: `comparison_shaping.py` — align per-dataset frequency shapes and compute deltas

**Files:**
- Create: `gnomad_link/mcp/comparison_shaping.py`
- Create: `tests/unit/mcp/test_comparison_shaping.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/mcp/test_comparison_shaping.py` with the full content below. The fixtures are already-shaped per-dataset dicts (exactly the shape `shape_variant_frequencies` emits): each has an `exome`/`genome` block with `populations: [{id, ac, an, af, homozygote_count}]` and a `summary.overall_af`. The shaping function must align populations across datasets, compute `max_minus_min_delta` per population, and assemble the top-level comparison block.

```python
"""Unit tests for comparison_shaping: aligning per-dataset frequency shapes.

Task C2.1 of the new-tools plan. compare_variant_across_datasets fans out
get_variant_frequencies per dataset, reuses shape_variant_frequencies per
dataset, then this module aligns the per-population AF rows across datasets and
computes deltas. Pure functions over already-shaped dicts; no service calls.
"""

from __future__ import annotations

from typing import Any


def _shaped(
    *,
    variant_id: str,
    dataset: str,
    overall_af: float,
    pops: dict[str, float],
) -> dict[str, Any]:
    """Build a minimal shape_variant_frequencies-style dict for one dataset."""
    return {
        "variant_id": variant_id,
        "dataset": dataset,
        "gene_symbol": "PCSK9",
        "major_consequence": "missense_variant",
        "exome": {
            "ac": 10,
            "an": 100_000,
            "af": overall_af,
            "homozygote_count": 0,
            "hemizygote_count": None,
            "populations": [
                {"id": pid, "ac": 1, "an": 1_000, "af": af, "homozygote_count": 0}
                for pid, af in pops.items()
            ],
        },
        "genome": None,
        "summary": {"overall_af": overall_af, "has_clinvar": None},
    }


def test_aligns_overall_af_by_dataset_for_present_datasets() -> None:
    from gnomad_link.mcp.comparison_shaping import build_comparison

    per_dataset = {
        "gnomad_r4": {"present": True, **_shaped(
            variant_id="1-55039974-G-T", dataset="gnomad_r4",
            overall_af=0.002, pops={"afr": 0.01, "nfe": 0.001},
        )},
        "gnomad_r3": {"present": True, **_shaped(
            variant_id="1-55039974-G-T", dataset="gnomad_r3",
            overall_af=0.0018, pops={"afr": 0.009, "nfe": 0.0012},
        )},
        "gnomad_r2_1": {"present": False},
    }

    comparison = build_comparison(per_dataset)

    assert comparison["overall_af_by_dataset"] == {
        "gnomad_r4": 0.002,
        "gnomad_r3": 0.0018,
    }
    assert "gnomad_r2_1" not in comparison["overall_af_by_dataset"]


def test_per_population_deltas_use_max_minus_min_across_present_datasets() -> None:
    from gnomad_link.mcp.comparison_shaping import build_comparison

    per_dataset = {
        "gnomad_r4": {"present": True, **_shaped(
            variant_id="1-55039974-G-T", dataset="gnomad_r4",
            overall_af=0.002, pops={"afr": 0.01, "nfe": 0.001},
        )},
        "gnomad_r3": {"present": True, **_shaped(
            variant_id="1-55039974-G-T", dataset="gnomad_r3",
            overall_af=0.0018, pops={"afr": 0.009, "nfe": 0.0012},
        )},
    }

    comparison = build_comparison(per_dataset)
    by_pop = {row["population"]: row for row in comparison["per_population_af_deltas"]}

    assert by_pop["afr"]["af_by_dataset"] == {"gnomad_r4": 0.01, "gnomad_r3": 0.009}
    assert abs(by_pop["afr"]["max_minus_min_delta"] - 0.001) < 1e-12
    assert abs(by_pop["nfe"]["max_minus_min_delta"] - 0.0002) < 1e-12


def test_population_present_in_only_one_dataset_has_zero_delta() -> None:
    from gnomad_link.mcp.comparison_shaping import build_comparison

    per_dataset = {
        "gnomad_r4": {"present": True, **_shaped(
            variant_id="1-1-A-T", dataset="gnomad_r4",
            overall_af=0.002, pops={"afr": 0.01, "mid": 0.05},
        )},
        "gnomad_r3": {"present": True, **_shaped(
            variant_id="1-1-A-T", dataset="gnomad_r3",
            overall_af=0.0018, pops={"afr": 0.009},
        )},
    }

    comparison = build_comparison(per_dataset)
    by_pop = {row["population"]: row for row in comparison["per_population_af_deltas"]}

    # mid only exists in r4: single value, delta is 0.0.
    assert by_pop["mid"]["af_by_dataset"] == {"gnomad_r4": 0.05}
    assert by_pop["mid"]["max_minus_min_delta"] == 0.0


def test_deltas_sorted_by_largest_delta_first() -> None:
    from gnomad_link.mcp.comparison_shaping import build_comparison

    per_dataset = {
        "gnomad_r4": {"present": True, **_shaped(
            variant_id="1-1-A-T", dataset="gnomad_r4",
            overall_af=0.5, pops={"afr": 0.5, "nfe": 0.10},
        )},
        "gnomad_r3": {"present": True, **_shaped(
            variant_id="1-1-A-T", dataset="gnomad_r3",
            overall_af=0.1, pops={"afr": 0.1, "nfe": 0.09},
        )},
    }

    comparison = build_comparison(per_dataset)
    deltas = comparison["per_population_af_deltas"]

    # afr swing (0.4) must sort before nfe swing (0.01).
    assert [row["population"] for row in deltas] == ["afr", "nfe"]


def test_genome_only_dataset_populations_are_aligned() -> None:
    from gnomad_link.mcp.comparison_shaping import build_comparison

    r3 = _shaped(
        variant_id="1-1-A-T", dataset="gnomad_r3",
        overall_af=0.02, pops={"afr": 0.02},
    )
    # Move the populations to the genome block; r3 is whole-genome.
    r3["genome"] = r3.pop("exome")
    r3["exome"] = None

    per_dataset = {
        "gnomad_r4": {"present": True, **_shaped(
            variant_id="1-1-A-T", dataset="gnomad_r4",
            overall_af=0.03, pops={"afr": 0.03},
        )},
        "gnomad_r3": {"present": True, **r3},
    }

    comparison = build_comparison(per_dataset)
    by_pop = {row["population"]: row for row in comparison["per_population_af_deltas"]}

    assert by_pop["afr"]["af_by_dataset"] == {"gnomad_r4": 0.03, "gnomad_r3": 0.02}
    assert abs(by_pop["afr"]["max_minus_min_delta"] - 0.01) < 1e-12


def test_no_present_datasets_yields_empty_comparison() -> None:
    from gnomad_link.mcp.comparison_shaping import build_comparison

    comparison = build_comparison(
        {"gnomad_r4": {"present": False}, "gnomad_r3": {"present": False}}
    )

    assert comparison["overall_af_by_dataset"] == {}
    assert comparison["per_population_af_deltas"] == []
```

- [ ] **Step 2: Run the new tests and confirm they fail**

Run: `uv run pytest tests/unit/mcp/test_comparison_shaping.py -q`
Expected: FAIL — collection/import error `ModuleNotFoundError: No module named 'gnomad_link.mcp.comparison_shaping'` (the module does not exist yet).

- [ ] **Step 3: Create the shaping module**

Create `gnomad_link/mcp/comparison_shaping.py` with the complete content below. `_iter_population_rows` reads whichever of `exome`/`genome` carries `populations` (a dataset may be exome-only, genome-only, or both); when a population appears in both sources of one dataset, the higher-AF row wins so the per-dataset value is the most-enriched observed AF, matching the `_top_enriched_population` convention in `shaping.py`.

```python
"""Pure helpers that align per-dataset variant-frequency shapes for comparison.

compare_variant_across_datasets calls get_variant_frequencies per dataset and
reuses shape_variant_frequencies to produce one compact dict per dataset. This
module consumes those already-shaped dicts (wrapped as {"present": True, ...} or
{"present": False}) and produces the top-level `comparison` block: overall AF by
dataset plus per-population AF deltas. No service or network access here.
"""

from __future__ import annotations

from typing import Any


def _iter_population_rows(shaped: dict[str, Any]) -> dict[str, float]:
    """Return {population_id: af} for one shaped dataset dict.

    Reads both exome and genome population lists. When the same population id is
    present in both sources, the higher AF wins so the recorded per-dataset value
    is the most-enriched observed allele frequency (mirrors shaping._top_enriched_population).
    Rows with af is None are skipped.
    """
    by_pop: dict[str, float] = {}
    for source_key in ("exome", "genome"):
        source = shaped.get(source_key)
        if not source:
            continue
        for pop in source.get("populations", []):
            pop_id = pop.get("id")
            af = pop.get("af")
            if pop_id is None or af is None:
                continue
            existing = by_pop.get(pop_id)
            if existing is None or af > existing:
                by_pop[pop_id] = af
    return by_pop


def build_comparison(per_dataset: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Assemble the comparison block from per-dataset shaped dicts.

    Args:
        per_dataset: dataset name -> {"present": bool, ...shaped frequency dict}.
            Absent datasets are {"present": False} and are skipped.

    Returns:
        {
            "overall_af_by_dataset": {dataset: overall_af, ...},
            "per_population_af_deltas": [
                {"population": str, "af_by_dataset": {dataset: af, ...},
                 "max_minus_min_delta": float},
                ...  # sorted by max_minus_min_delta descending, then population asc
            ],
        }
    """
    overall_af_by_dataset: dict[str, float] = {}
    # population -> dataset -> af
    af_by_pop_dataset: dict[str, dict[str, float]] = {}

    for dataset, entry in per_dataset.items():
        if not entry.get("present"):
            continue
        summary = entry.get("summary") or {}
        overall_af = summary.get("overall_af")
        if overall_af is not None:
            overall_af_by_dataset[dataset] = overall_af
        for pop_id, af in _iter_population_rows(entry).items():
            af_by_pop_dataset.setdefault(pop_id, {})[dataset] = af

    deltas: list[dict[str, Any]] = []
    for pop_id, af_by_dataset in af_by_pop_dataset.items():
        values = list(af_by_dataset.values())
        delta = (max(values) - min(values)) if len(values) > 1 else 0.0
        deltas.append(
            {
                "population": pop_id,
                "af_by_dataset": af_by_dataset,
                "max_minus_min_delta": delta,
            }
        )
    deltas.sort(key=lambda row: (-row["max_minus_min_delta"], row["population"]))

    return {
        "overall_af_by_dataset": overall_af_by_dataset,
        "per_population_af_deltas": deltas,
    }
```

- [ ] **Step 4: Run the new tests and confirm they pass**

Run: `uv run pytest tests/unit/mcp/test_comparison_shaping.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Full local CI gate**

Run: `make ci-local`
Expected: PASS (format, lint, `lint-loc`, typecheck, unit tests) — confirms the new module is under the LOC cap and type-clean before committing.

- [ ] **Step 6: Commit**

```
git add gnomad_link/mcp/comparison_shaping.py tests/unit/mcp/test_comparison_shaping.py
git commit -m "feat(mcp): add comparison_shaping to align per-dataset AF and compute deltas"
```

---

### Task C2.2: `compare_variant_across_datasets` tool — fan-out, partial success, auto-liftover

**Files:**
- Create: `gnomad_link/mcp/tools/comparison.py`
- Modify: `gnomad_link/mcp/tools/__init__.py`
- Modify: `gnomad_link/mcp/resources.py`
- Modify: `tests/unit/mcp/test_mcp_facade_surface.py`
- Create: `tests/unit/mcp/test_compare_variant.py`

- [ ] **Step 1: Write the failing tests**

First add the tool name to the surface parity set. In `tests/unit/mcp/test_mcp_facade_surface.py`, extend `EXPECTED_TOOLS`:

```python
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
    "get_gnomad_diagnostics",
    "compare_variant_across_datasets",
}
```

Then create `tests/unit/mcp/test_compare_variant.py` with the full content below. The stub raises `DataNotFoundError` for a dataset to exercise partial success, returns lifted results from `liftover_variant`, and records every call so the test can assert the GRCh38->GRCh37 liftover path fired for `gnomad_r2_1`.

```python
"""Tool-level tests for compare_variant_across_datasets.

Task C2.2 of the new-tools plan. The tool fans out get_variant_frequencies per
dataset (reusing shape_variant_frequencies), tolerates per-dataset 404s as
{present: false}, and for gnomad_r2_1 (GRCh37) with a GRCh38-style id and
auto_liftover=True converts the id first via liftover_variant.
"""

from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.api import DataNotFoundError, GnomadApiError
from gnomad_link.models import VariantDataSource, VariantFrequencyResponse
from gnomad_link.models.variant_models import PopulationFrequency


def _structured(result: Any) -> dict[str, Any]:
    return result.structured_content or {}


def _freq(
    variant_id: str,
    dataset: str,
    *,
    overall_an: int = 100_000,
    overall_ac: int = 200,
    afr_ac: int = 100,
    nfe_ac: int = 10,
) -> VariantFrequencyResponse:
    exome = VariantDataSource(
        ac=overall_ac,
        an=overall_an,
        homozygote_count=0,
        populations=[
            PopulationFrequency.model_validate(
                {"id": "afr", "ac": afr_ac, "an": 10_000, "homozygote_count": 0}
            ),
            PopulationFrequency.model_validate(
                {"id": "nfe", "ac": nfe_ac, "an": 50_000, "homozygote_count": 0}
            ),
        ],
    )
    return VariantFrequencyResponse(
        variant_id=variant_id,
        dataset=dataset,
        gene_symbol="PCSK9",
        major_consequence="missense_variant",
        exome=exome,
        genome=None,
    )


class _StubService:
    """FrequencyService stub. Maps (variant_id, dataset) -> response or raises."""

    def __init__(
        self,
        *,
        freq_by_dataset: dict[str, VariantFrequencyResponse | BaseException],
        liftover_result: list[dict[str, Any]] | None = None,
    ) -> None:
        self._freq_by_dataset = freq_by_dataset
        self._liftover_result = liftover_result if liftover_result is not None else []
        self.freq_calls: list[tuple[str, str]] = []
        self.liftover_calls: list[tuple[str, str]] = []

    async def get_variant_frequencies(
        self, variant_id: str, dataset: str
    ) -> VariantFrequencyResponse:
        self.freq_calls.append((variant_id, dataset))
        outcome = self._freq_by_dataset[dataset]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    async def liftover_variant(
        self, source_variant_id: str, reference_genome: str
    ) -> list[dict[str, Any]]:
        self.liftover_calls.append((source_variant_id, reference_genome))
        return list(self._liftover_result)


@pytest.mark.asyncio
async def test_compares_two_present_datasets_and_emits_deltas() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubService(
        freq_by_dataset={
            "gnomad_r4": _freq("1-55039974-G-T", "gnomad_r4", afr_ac=100),
            "gnomad_r3": _freq("1-55039974-G-T", "gnomad_r3", afr_ac=80),
        }
    )
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "compare_variant_across_datasets",
        {"variant_id": "1-55039974-G-T", "datasets": ["gnomad_r4", "gnomad_r3"]},
    )
    payload = _structured(result)

    assert payload.get("success") is not False, payload
    assert payload["variant_id"] == "1-55039974-G-T"
    assert payload["datasets"]["gnomad_r4"]["present"] is True
    assert payload["datasets"]["gnomad_r3"]["present"] is True
    overall = payload["comparison"]["overall_af_by_dataset"]
    assert set(overall) == {"gnomad_r4", "gnomad_r3"}
    by_pop = {
        row["population"]: row for row in payload["comparison"]["per_population_af_deltas"]
    }
    # afr: r4 100/10000 = 0.01 vs r3 80/10000 = 0.008 -> delta 0.002.
    assert abs(by_pop["afr"]["max_minus_min_delta"] - 0.002) < 1e-12


@pytest.mark.asyncio
async def test_missing_dataset_marked_present_false_partial_success() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubService(
        freq_by_dataset={
            "gnomad_r4": _freq("1-55039974-G-T", "gnomad_r4"),
            "gnomad_r3": DataNotFoundError("not in r3"),
        }
    )
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "compare_variant_across_datasets",
        {"variant_id": "1-55039974-G-T", "datasets": ["gnomad_r4", "gnomad_r3"]},
    )
    payload = _structured(result)

    assert payload.get("success") is not False, payload
    assert payload["datasets"]["gnomad_r4"]["present"] is True
    assert payload["datasets"]["gnomad_r3"] == {"present": False}
    # Only the present dataset contributes to overall comparison.
    assert set(payload["comparison"]["overall_af_by_dataset"]) == {"gnomad_r4"}


@pytest.mark.asyncio
async def test_all_datasets_missing_returns_upstream_unavailable() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    # A real upstream error (GnomadApiError), NOT DataNotFoundError: the latter is
    # classified as "dataset absent" (partial success), whereas an upstream failure
    # for EVERY dataset is what collapses the whole call to upstream_unavailable.
    stub = _StubService(
        freq_by_dataset={
            "gnomad_r4": GnomadApiError("upstream 503"),
            "gnomad_r3": GnomadApiError("upstream 503"),
        }
    )
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "compare_variant_across_datasets",
        {"variant_id": "1-55039974-G-T", "datasets": ["gnomad_r4", "gnomad_r3"]},
    )
    payload = _structured(result)

    assert payload["success"] is False
    assert payload["error_code"] == "upstream_unavailable"


@pytest.mark.asyncio
async def test_auto_liftover_converts_grch38_id_for_r2_1() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubService(
        freq_by_dataset={
            "gnomad_r4": _freq("17-7673803-G-A", "gnomad_r4"),
            "gnomad_r2_1": _freq("17-7577121-G-A", "gnomad_r2_1"),
        },
        liftover_result=[
            {
                "source": {"variant_id": "17-7673803-G-A", "reference_genome": "GRCh38"},
                "liftover": {"variant_id": "17-7577121-G-A", "reference_genome": "GRCh37"},
                "datasets": ["gnomad_r2_1", "gnomad_r4"],
            }
        ],
    )
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "compare_variant_across_datasets",
        {
            "variant_id": "17-7673803-G-A",
            "datasets": ["gnomad_r4", "gnomad_r2_1"],
            "auto_liftover": True,
        },
    )
    payload = _structured(result)

    assert payload.get("success") is not False, payload
    # Liftover was invoked GRCh38 -> GRCh37 for the r2_1 leg.
    assert stub.liftover_calls == [("17-7673803-G-A", "GRCh38")]
    # The r2_1 frequency lookup used the lifted GRCh37 id.
    assert ("17-7577121-G-A", "gnomad_r2_1") in stub.freq_calls
    r2 = payload["datasets"]["gnomad_r2_1"]
    assert r2["present"] is True
    assert r2["lifted_variant_id"] == "17-7577121-G-A"
    assert any("GRCh37" in note for note in payload["build_notes"])


@pytest.mark.asyncio
async def test_auto_liftover_no_mapping_marks_r2_1_present_false() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubService(
        freq_by_dataset={
            "gnomad_r4": _freq("17-7673803-G-A", "gnomad_r4"),
            # r2_1 should never be queried because liftover yields no mapping.
            "gnomad_r2_1": _freq("unused", "gnomad_r2_1"),
        },
        liftover_result=[],
    )
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "compare_variant_across_datasets",
        {
            "variant_id": "17-7673803-G-A",
            "datasets": ["gnomad_r4", "gnomad_r2_1"],
            "auto_liftover": True,
        },
    )
    payload = _structured(result)

    assert payload.get("success") is not False, payload
    assert payload["datasets"]["gnomad_r2_1"] == {"present": False}
    assert stub.liftover_calls == [("17-7673803-G-A", "GRCh38")]
    # r2_1 frequencies never fetched (no lifted id).
    assert all(d != "gnomad_r2_1" for _, d in stub.freq_calls)


@pytest.mark.asyncio
async def test_next_commands_point_to_clinvar_and_carrier() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubService(
        freq_by_dataset={"gnomad_r4": _freq("1-55039974-G-T", "gnomad_r4")}
    )
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "compare_variant_across_datasets",
        {"variant_id": "1-55039974-G-T", "datasets": ["gnomad_r4"]},
    )
    payload = _structured(result)

    next_tools = [cmd["tool"] for cmd in payload["_meta"]["next_commands"]]
    assert "get_clinvar_variant_details" in next_tools
    assert "compute_carrier_frequency" in next_tools
    assert "compare_variant_across_datasets" not in next_tools  # no self-reference
    assert len(next_tools) <= 3
    # Research-use meta is preserved by run_mcp_tool.
    assert payload["_meta"]["unsafe_for_clinical_use"] is True


@pytest.mark.asyncio
async def test_tool_has_read_only_open_world_annotations_and_tag() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubService(freq_by_dataset={})
    mcp = create_gnomad_mcp(service_factory=lambda: stub)
    tools_by_name = {tool.name: tool for tool in await mcp.list_tools()}
    tool = tools_by_name["compare_variant_across_datasets"]

    assert tool.tags == {"variant"}
    assert tool.annotations is not None
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.openWorldHint is True
    assert tool.output_schema is not None
```

- [ ] **Step 2: Run the new tests and confirm they fail**

Run: `uv run pytest tests/unit/mcp/test_compare_variant.py tests/unit/mcp/test_mcp_facade_surface.py::test_capabilities_tools_match_facade_tools -q`
Expected: FAIL — `test_compare_variant.py` fails because the `compare_variant_across_datasets` tool is not registered (`KeyError`/missing tool), and the parity test fails because `EXPECTED_TOOLS` now contains a name that is neither registered nor in the capabilities `tools` list.

- [ ] **Step 3: Create the tool module**

Create `gnomad_link/mcp/tools/comparison.py` with the complete content below. It reuses `shape_variant_frequencies` per dataset with identical compact knobs, treats `DataNotFoundError`/`VariantNotFoundError` as `{present: false}` (partial success), raises `upstream_unavailable` only when every dataset failed for an upstream reason, and for `gnomad_r2_1` with a GRCh38-style id and `auto_liftover=True` converts the id via `service.liftover_variant` (GRCh38 -> GRCh37) before fetching.

```python
"""Cross-dataset comparison tools: compare_variant_across_datasets."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.api import DataNotFoundError, GnomadApiError
from gnomad_link.api.base_client import VariantNotFoundError
from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.comparison_shaping import build_comparison
from gnomad_link.mcp.errors import McpErrorContext, McpToolError, mcp_tool_error, run_mcp_tool
from gnomad_link.mcp.schema_relax import relax_output_schema
from gnomad_link.mcp.shaping import shape_variant_frequencies
from gnomad_link.services import FrequencyService

# Reuse the autosomal grammar from the headline frequency tool. Mitochondrial
# variants are build-stable and not meaningfully comparable across releases here.
_AUTOSOMAL_VARIANT_ID_PATTERN = r"^([1-9]|1\d|2[0-2]|X|Y)-\d+-[ACGT]+-[ACGT]+$"

_DEFAULT_DATASETS = ["gnomad_r4", "gnomad_r3", "gnomad_r2_1"]

# Datasets and their reference build. Only gnomad_r2_1 is GRCh37.
_GRCH37_DATASETS = {"gnomad_r2_1"}

_COMPARE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "variant_id": {"type": "string"},
        "datasets": {"type": "object"},
        "comparison": {
            "type": "object",
            "properties": {
                "overall_af_by_dataset": {"type": "object"},
                "per_population_af_deltas": {"type": "array", "items": {"type": "object"}},
            },
        },
        "build_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["variant_id", "datasets", "comparison"],
    "additionalProperties": True,
}

# gnomAD does not return upstream errors for a build-mismatched coordinate; it
# simply 404s. We treat these as "absent in that dataset" rather than failures.
_ABSENT_EXCEPTIONS = (DataNotFoundError, VariantNotFoundError)
_UPSTREAM_EXCEPTIONS = (GnomadApiError, TimeoutError)


async def _resolve_r2_1_id(
    service: FrequencyService, variant_id: str, *, auto_liftover: bool
) -> tuple[str | None, str | None]:
    """Return (lifted_grch37_id, note) for the gnomad_r2_1 leg.

    The supplied variant_id is GRCh38 (it passed the autosomal grammar and the
    caller is comparing GRCh38 releases). For r2_1 (GRCh37) we must lift it.
    Returns (None, note) when auto_liftover is off or no mapping exists, which
    the caller records as {present: false}.
    """
    if not auto_liftover:
        return None, (
            "gnomad_r2_1 is GRCh37; auto_liftover=False so the GRCh38 id was not "
            "converted and r2_1 was skipped. Call liftover_variant to compare it."
        )
    results = await service.liftover_variant(variant_id, "GRCh38")
    for item in results:
        lifted = (item.get("liftover") or {}).get("variant_id")
        if lifted:
            return lifted, (
                f"gnomad_r2_1 (GRCh37) used lifted id {lifted} from GRCh38 {variant_id}."
            )
    return None, (
        f"gnomad_r2_1 (GRCh37) skipped: no liftover mapping found for {variant_id}."
    )


def register_comparison_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="compare_variant_across_datasets",
        title="Compare One Variant Across gnomAD Datasets",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=relax_output_schema(_COMPARE_OUTPUT_SCHEMA),
        tags={"variant"},
    )
    async def compare_variant_across_datasets(
        variant_id: Annotated[
            str,
            Field(
                description="GRCh38 CHROM-POS-REF-ALT id (e.g. 1-55039974-G-T). r2_1 is auto-lifted to GRCh37.",
                min_length=5,
                max_length=200,
                pattern=_AUTOSOMAL_VARIANT_ID_PATTERN,
                examples=["1-55039974-G-T", "17-7673803-G-A"],
            ),
        ],
        datasets: Annotated[
            list[str] | None,
            Field(
                description="Datasets to compare. None compares gnomad_r4, gnomad_r3, gnomad_r2_1.",
                examples=[["gnomad_r4", "gnomad_r3", "gnomad_r2_1"]],
            ),
        ] = None,
        populations: Annotated[
            list[str] | None,
            Field(
                description="Restrict per-population rows to these codes (e.g. ['afr','nfe']). None keeps all.",
                examples=[["afr", "nfe"]],
            ),
        ] = None,
        auto_liftover: Annotated[
            bool,
            Field(
                description="Lift the GRCh38 id to GRCh37 for gnomad_r2_1. Off skips r2_1 with a build note.",
            ),
        ] = True,
    ) -> dict[str, Any]:
        """Use this when a caller wants to see how one variant's allele frequencies shift across gnomAD releases (r4 vs r3 vs r2_1) and which populations diverge most. Datasets that lack the variant are marked present=false (partial success); the GRCh37 gnomad_r2_1 leg is auto-lifted from the GRCh38 id. Pair with get_clinvar_variant_details for clinical context. Returns ~3-8kB."""

        async def call() -> dict[str, Any]:
            selected = datasets if datasets is not None else list(_DEFAULT_DATASETS)
            service = service_factory()
            per_dataset: dict[str, dict[str, Any]] = {}
            build_notes: list[str] = []
            upstream_failures = 0
            attempted = 0

            for dataset in selected:
                lookup_id = variant_id
                lifted_id: str | None = None
                if dataset in _GRCH37_DATASETS:
                    lifted_id, note = await _resolve_r2_1_id(
                        service, variant_id, auto_liftover=auto_liftover
                    )
                    build_notes.append(note)
                    if lifted_id is None:
                        per_dataset[dataset] = {"present": False}
                        continue
                    lookup_id = lifted_id

                attempted += 1
                try:
                    response = await service.get_variant_frequencies(lookup_id, dataset)
                except _ABSENT_EXCEPTIONS:
                    per_dataset[dataset] = {"present": False}
                    continue
                except _UPSTREAM_EXCEPTIONS:
                    upstream_failures += 1
                    per_dataset[dataset] = {"present": False}
                    continue

                shaped = shape_variant_frequencies(
                    response,
                    populations=populations,
                    include_subcohorts=False,
                    include_sex_split=False,
                    exclude_zero_populations=True,
                )
                entry: dict[str, Any] = {"present": True, **shaped}
                if lifted_id is not None:
                    entry["lifted_variant_id"] = lifted_id
                per_dataset[dataset] = entry

            present_count = sum(1 for e in per_dataset.values() if e.get("present"))
            # Fail the whole call only when every attempted lookup failed for an
            # upstream reason (not simple absence). Pure 404s -> partial success.
            if present_count == 0 and attempted > 0 and upstream_failures == attempted:
                raise GnomadApiError(
                    "All requested datasets failed upstream for "
                    f"{variant_id}; none could be compared."
                )

            comparison = build_comparison(per_dataset)
            payload: dict[str, Any] = {
                "variant_id": variant_id,
                "datasets": per_dataset,
                "comparison": comparison,
                "build_notes": build_notes,
            }
            payload["_meta"] = {
                "next_commands": [
                    {
                        "tool": "get_clinvar_variant_details",
                        "arguments": {"variant_id": variant_id, "reference_genome": "GRCh38"},
                    },
                    {
                        "tool": "compute_carrier_frequency",
                        # inheritance is REQUIRED (no default) on compute_carrier_frequency;
                        # advertise a concrete AR call so the chained command is valid.
                        "arguments": {
                            "variant_id": variant_id,
                            "inheritance": "AR",
                            "dataset": "gnomad_r4",
                        },
                    },
                ]
            }
            return payload

        return await run_mcp_tool(
            "compare_variant_across_datasets",
            call,
            context=McpErrorContext(
                tool_name="compare_variant_across_datasets", variant_id=variant_id
            ),
        )

    # mcp_tool_error / McpToolError are imported for parity with sibling tool
    # modules; run_mcp_tool already wraps the call() body in the error boundary.
    _ = (mcp_tool_error, McpToolError)
```

Note: the final `_ = (mcp_tool_error, McpToolError)` line is only present if Ruff flags the imports as unused. If `run_mcp_tool` alone is used (it is), drop those two names from the import and delete the `_ = (...)` line so the import list is exactly `from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool`. Prefer the minimal import:

```python
from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool
```

and remove the trailing `_ = (mcp_tool_error, McpToolError)` line entirely.

- [ ] **Step 4: Wire the new module into the facade**

In `gnomad_link/mcp/tools/__init__.py`, add the import alongside the existing ones:

```python
from gnomad_link.mcp.tools.comparison import register_comparison_tools
```

and add the call inside `register_gnomad_tools`, after `register_variant_tools`:

```python
    register_variant_tools(mcp, service_factory=service_factory)
    register_comparison_tools(mcp, service_factory=service_factory)
```

- [ ] **Step 5: Sync the capabilities resource (parity gate)**

In `gnomad_link/mcp/resources.py`, append `"compare_variant_across_datasets"` to the `tools` list (after `"get_variant_details"`):

```python
        "tools": [
            "get_server_capabilities",
            "get_variant_frequencies",
            "get_variant_details",
            "compare_variant_across_datasets",
            "get_gene_details",
            ...
        ],
```

Add a `token_cost_hints` entry (must be <=80 chars):

```python
            "compare_variant_across_datasets": "~3-8kB (dataset/liftover dependent)",
```

Add it to the `variant` category under `tool_categories`:

```python
            "variant": [
                "get_variant_frequencies",
                "get_variant_details",
                "compare_variant_across_datasets",
                "get_mitochondrial_variant",
                "get_structural_variant",
            ],
```

- [ ] **Step 6: Run the focused tests and confirm they pass**

Run: `uv run pytest tests/unit/mcp/test_compare_variant.py tests/unit/mcp/test_mcp_facade_surface.py -q`
Expected: PASS (all `test_compare_variant.py` cases plus the full surface suite, including `test_capabilities_tools_match_facade_tools` and `test_capabilities_resource_lists_token_cost_hints`, green).

- [ ] **Step 7: Full local CI**

Run: `make ci-local`
Expected: PASS (format-check, lint, lint-loc, typecheck, and unit tests all green; `comparison.py` and `comparison_shaping.py` are each well under the 600-LOC cap).

- [ ] **Step 8: Commit**

```
git add gnomad_link/mcp/tools/comparison.py gnomad_link/mcp/tools/__init__.py gnomad_link/mcp/resources.py tests/unit/mcp/test_compare_variant.py tests/unit/mcp/test_mcp_facade_surface.py
git commit -m "feat(mcp): add compare_variant_across_datasets with partial success and auto-liftover"

---

## Phase C3: compute_carrier_frequency — derive Hardy-Weinberg carrier/affected frequencies (with Wilson CIs) from a single gnomAD allele frequency, for AR/AD/XL inheritance

This phase adds one new MCP tool, `compute_carrier_frequency`, that performs **pure local math** on top of the existing `FrequencyService.get_variant_frequencies`. It introduces no new GraphQL documents, no new `UnifiedGnomadClient` methods, and no new `FrequencyService` method — it composes the existing variant-frequency call. All arithmetic lives in a new pure-function module `gnomad_link/services/carrier_math.py` (golden-tested, no MCP, no I/O), and the tool wiring lives in a new `gnomad_link/mcp/tools/carrier.py` registered exactly like the other `register_*_tools` functions.

**Math contract (all closed-form, no scipy):**
- AR: `p = 1 - q` where `q = AF`; carrier (HWE) `= 2*p*q`; affected `= q**2`. `method="hom_corrected"` uses the observed variant carrier rate `VCR = (ac - 2*homozygote_count) / (an / 2)`.
- AD: affected-or-carrier `= 1 - (1 - q)**2` (`== 2q - q**2`); literature-derived (Whiffin 2017).
- XL: from the sex-split rows gnomAD already returns (ids like `XX`, `XY`, `afr_XX`, `afr_XY`): `female_carrier = 2*q_XX`; `affected_female = q_XX**2`; `affected_male = q_XY` (hemizygous AF — no `2x`, no square).
- Wilson 95% CI on each AF (`z = 1.96`) propagated through the same carrier formula, surfaced as `ci_low`/`ci_high`.
- Edge cases: `an == 0` -> `carrier_frequency = None` (NOT `0`); `ac == 0` -> values computed (zero) but the population flagged so callers know the carrier estimate is a floor.

**Citations embedded in the response and docstring:** Schrodi 2015 (Hum Genet, doi:10.1007/s00439-015-1551-8); Karczewski 2020 (gnomAD); Guo 2019 / Zhu 2022 (variant carrier rate); Hotakainen 2025 / Kandolin 2024 (X-linked). The response carries an `assumptions_note` (HWE, random mating, complete penetrance, single-variant, minimum estimate) and preserves `unsafe_for_clinical_use` semantics.

### Files

- **Create:** `gnomad_link/services/carrier_math.py` — pure functions: `wilson_ci`, `ar_carrier`, `ar_affected`, `variant_carrier_rate`, `ad_affected_or_carrier`, `xl_female_carrier`, `xl_affected_female`, `xl_affected_male`. No imports beyond `math`/typing. Stays well under 600 LOC.
- **Create:** `gnomad_link/mcp/tools/carrier.py` — `register_carrier_tools(mcp, *, service_factory)` registering the single `compute_carrier_frequency` tool. Stays under 600 LOC.
- **Modify:** `gnomad_link/mcp/tools/__init__.py` — one import + one call line.
- **Modify:** `gnomad_link/mcp/resources.py` — append the tool to `tools`, `token_cost_hints`, and `tool_categories["variant"]`.
- **Create:** `tests/unit/services/test_carrier_math.py` — golden-value unit tests for the pure math (C3.1).
- **Modify:** `tests/unit/mcp/test_mcp_facade_surface.py` — add `compute_carrier_frequency` to `EXPECTED_TOOLS`.
- **Create:** `tests/unit/mcp/test_carrier_tool.py` — offline tool tests for AR (C3.2), then AD + XL (C3.3).

---

### Task C3.1: Pure carrier math module + golden-value unit tests

**Files:**
- Create: `gnomad_link/services/carrier_math.py`
- Create: `tests/unit/services/test_carrier_math.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/services/test_carrier_math.py`:

```python
from __future__ import annotations

import math

import pytest

from gnomad_link.services.carrier_math import (
    ad_affected_or_carrier,
    ar_affected,
    ar_carrier,
    variant_carrier_rate,
    wilson_ci,
    xl_affected_female,
    xl_affected_male,
    xl_female_carrier,
)


def test_ar_carrier_cftr_like_golden() -> None:
    # CFTR-like q = 0.023 -> 2pq = 0.044942
    assert ar_carrier(0.023) == pytest.approx(0.044942, abs=1e-9)


def test_ar_affected_cftr_like_golden() -> None:
    # q = 0.023 -> q**2 = 0.000529
    assert ar_affected(0.023) == pytest.approx(0.000529, abs=1e-9)


def test_ar_carrier_second_golden() -> None:
    # q = 0.011 -> 2pq = 0.021758
    assert ar_carrier(0.011) == pytest.approx(0.021758, abs=1e-9)


def test_ar_carrier_zero_af_is_zero() -> None:
    assert ar_carrier(0.0) == 0.0
    assert ar_affected(0.0) == 0.0


def test_ad_affected_or_carrier_equals_two_q_minus_q_squared() -> None:
    q = 0.023
    assert ad_affected_or_carrier(q) == pytest.approx(2 * q - q**2, abs=1e-12)
    assert ad_affected_or_carrier(q) == pytest.approx(1 - (1 - q) ** 2, abs=1e-12)


def test_variant_carrier_rate_hom_corrected() -> None:
    # ac=100, hom=10, an=20000 -> (100 - 20) / (20000/2) = 80 / 10000 = 0.008
    assert variant_carrier_rate(ac=100, homozygote_count=10, an=20000) == pytest.approx(
        0.008, abs=1e-12
    )


def test_variant_carrier_rate_zero_an_is_none() -> None:
    assert variant_carrier_rate(ac=0, homozygote_count=0, an=0) is None


def test_xl_female_carrier_uses_two_q() -> None:
    # q_XX = 0.01 -> 2 * 0.01 = 0.02
    assert xl_female_carrier(0.01) == pytest.approx(0.02, abs=1e-12)


def test_xl_affected_female_is_q_squared() -> None:
    assert xl_affected_female(0.01) == pytest.approx(0.0001, abs=1e-12)


def test_xl_affected_male_is_hemizygous_af() -> None:
    # Hemizygous: no 2x, no square; affected male == q_XY.
    assert xl_affected_male(0.01) == pytest.approx(0.01, abs=1e-12)


def test_wilson_ci_known_value() -> None:
    # af = 0.5, n = 100, z = 1.96 -> closed-form center/half.
    low, high = wilson_ci(af=0.5, n=100)
    z = 1.96
    center = (0.5 + z * z / (2 * 100)) / (1 + z * z / 100)
    half = (z / (1 + z * z / 100)) * math.sqrt(0.5 * 0.5 / 100 + z * z / (4 * 100 * 100))
    assert low == pytest.approx(center - half, abs=1e-12)
    assert high == pytest.approx(center + half, abs=1e-12)


def test_wilson_ci_bounds_are_clamped_to_unit_interval() -> None:
    low, high = wilson_ci(af=0.001, n=10)
    assert low >= 0.0
    assert high <= 1.0


def test_wilson_ci_zero_n_is_none() -> None:
    assert wilson_ci(af=0.0, n=0) == (None, None)
```

- [ ] **Step 2: Run the tests, expect failure**

Run: `make test-unit ARGS="tests/unit/services/test_carrier_math.py"`
(if the Makefile does not forward `ARGS`, run `uv run pytest tests/unit/services/test_carrier_math.py`)
Expected: FAIL — `ModuleNotFoundError: No module named 'gnomad_link.services.carrier_math'`.

- [ ] **Step 3: Implement the pure math module**

Create `gnomad_link/services/carrier_math.py`:

```python
"""Pure Hardy-Weinberg carrier/affected-frequency math for compute_carrier_frequency.

No I/O, no gnomAD, no MCP. Every function is closed-form and golden-tested.

References:
- Schrodi et al. 2015, Hum Genet, doi:10.1007/s00439-015-1551-8 (2pq / q^2 carrier
  framework and confidence-interval concept).
- Karczewski et al. 2020 (gnomAD allele-frequency reference).
- Guo et al. 2019; Zhu et al. 2022 (homozygote-corrected variant carrier rate).
- Hotakainen et al. 2025; Kandolin et al. 2024 (X-linked sex-split estimation).

All estimates assume Hardy-Weinberg equilibrium, random mating, complete
penetrance, a single causal variant, and represent a minimum estimate.
"""

from __future__ import annotations

import math

# Standard normal quantile for a two-sided 95% interval.
_WILSON_Z = 1.96


def ar_carrier(q: float) -> float:
    """Autosomal-recessive carrier frequency under HWE: 2*p*q (p = 1 - q)."""
    p = 1.0 - q
    return 2.0 * p * q


def ar_affected(q: float) -> float:
    """Autosomal-recessive affected frequency under HWE: q**2."""
    return q * q


def variant_carrier_rate(*, ac: int, homozygote_count: int, an: int) -> float | None:
    """Homozygote-corrected variant carrier rate: (ac - 2*hom) / (an / 2).

    Returns None when an == 0 (carrier frequency is undefined, not zero).
    """
    if an <= 0:
        return None
    return (ac - 2 * homozygote_count) / (an / 2.0)


def ad_affected_or_carrier(q: float) -> float:
    """Autosomal-dominant affected-or-carrier frequency: 1 - (1 - q)**2.

    Algebraically equal to 2q - q**2 (Whiffin et al. 2017).
    """
    return 1.0 - (1.0 - q) ** 2


def xl_female_carrier(q_xx: float) -> float:
    """X-linked heterozygous female carrier frequency: 2*q_XX (HWE)."""
    return 2.0 * q_xx


def xl_affected_female(q_xx: float) -> float:
    """X-linked homozygous affected female frequency: q_XX**2 (HWE)."""
    return q_xx * q_xx


def xl_affected_male(q_xy: float) -> float:
    """X-linked affected male frequency: hemizygous AF (no 2x, no square)."""
    return q_xy


def wilson_ci(*, af: float, n: int) -> tuple[float | None, float | None]:
    """Closed-form Wilson 95% score interval for a binomial proportion.

    af is the point estimate (k/n); n is the allele number. Returns (low, high)
    clamped to [0, 1]. Returns (None, None) when n <= 0 so callers do not emit a
    spurious zero-width interval.
    """
    if n <= 0:
        return (None, None)
    z = _WILSON_Z
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (af + z2 / (2.0 * n)) / denom
    half = (z / denom) * math.sqrt(af * (1.0 - af) / n + z2 / (4.0 * n * n))
    low = max(0.0, center - half)
    high = min(1.0, center + half)
    return (low, high)
```

- [ ] **Step 4: Run the tests, expect pass**

Run: `uv run pytest tests/unit/services/test_carrier_math.py`
Expected: PASS — all 13 tests green.

- [ ] **Step 5: Verify**

Run: `make ci-local`
Expected: PASS (format, lint, lint-loc, typecheck, tests all green).

- [ ] **Step 6: Commit**

```
git add gnomad_link/services/carrier_math.py tests/unit/services/test_carrier_math.py
git commit -m "feat(mcp): add pure HWE carrier-frequency math with Wilson CIs and golden tests"
```

---

### Task C3.2: Register compute_carrier_frequency (AR) + capabilities/parity sync + tool test

**Files:**
- Create: `gnomad_link/mcp/tools/carrier.py`
- Modify: `gnomad_link/mcp/tools/__init__.py`
- Modify: `gnomad_link/mcp/resources.py`
- Modify: `tests/unit/mcp/test_mcp_facade_surface.py`
- Create: `tests/unit/mcp/test_carrier_tool.py`

- [ ] **Step 1: Write failing tests**

Add `compute_carrier_frequency` to `EXPECTED_TOOLS` in `tests/unit/mcp/test_mcp_facade_surface.py`:

```python
    "search_variants",  # deprecated alias retained for one release
    "compute_carrier_frequency",
    "get_gnomad_diagnostics",
```

Create `tests/unit/mcp/test_carrier_tool.py`:

```python
from __future__ import annotations

import pytest

from gnomad_link.models import (
    PopulationFrequency,
    VariantDataSource,
    VariantFrequencyResponse,
)


def _ar_response() -> VariantFrequencyResponse:
    # CFTR-like overall q = 0.023 (ac=460, an=20000), one population row.
    return VariantFrequencyResponse(
        variant_id="7-117559590-ATCT-A",
        dataset="gnomad_r4",
        exome=VariantDataSource(
            ac=460,
            an=20000,
            homozygote_count=5,
            populations=[
                PopulationFrequency(id="nfe", ac=460, an=20000, homozygote_count=5),
                PopulationFrequency(id="afr", ac=0, an=8000, homozygote_count=0),
            ],
        ),
        genome=None,
        gene_symbol="CFTR",
        major_consequence="frameshift_variant",
    )


class _StubFreqService:
    def __init__(self, response: VariantFrequencyResponse) -> None:
        self._response = response
        self.calls: list[tuple[str, str]] = []

    async def get_variant_frequencies(
        self, variant_id: str, dataset: str = "gnomad_r4"
    ) -> VariantFrequencyResponse:
        self.calls.append((variant_id, dataset))
        return self._response


@pytest.mark.asyncio
async def test_compute_carrier_frequency_ar_overall_golden() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _StubFreqService(_ar_response())
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool(
        "compute_carrier_frequency",
        {"variant_id": "7-117559590-ATCT-A", "inheritance": "AR"},
    )
    payload = result.structured_content or {}

    assert payload["inheritance"] == "AR"
    assert payload["overall"]["af"] == pytest.approx(0.023, abs=1e-6)
    assert payload["overall"]["carrier_frequency"] == pytest.approx(0.044942, abs=1e-6)
    assert payload["overall"]["affected_frequency"] == pytest.approx(0.000529, abs=1e-6)
    # Wilson CI present and brackets the point estimate.
    assert payload["overall"]["ci_low"] < payload["overall"]["carrier_frequency"]
    assert payload["overall"]["ci_high"] > payload["overall"]["carrier_frequency"]


@pytest.mark.asyncio
async def test_compute_carrier_frequency_per_population_and_summary() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _StubFreqService(_ar_response())
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool(
        "compute_carrier_frequency",
        {"variant_id": "7-117559590-ATCT-A", "inheritance": "AR"},
    )
    payload = result.structured_content or {}

    by_pop = {row["population"]: row for row in payload["per_population"]}
    assert by_pop["nfe"]["carrier_frequency"] == pytest.approx(0.044942, abs=1e-6)
    # afr has ac == 0 -> carrier present but zero, row still emitted.
    assert by_pop["afr"]["af"] == pytest.approx(0.0, abs=1e-12)
    assert by_pop["afr"]["carrier_frequency"] == pytest.approx(0.0, abs=1e-12)
    assert payload["summary"]["max_carrier_frequency_population"] == "nfe"


@pytest.mark.asyncio
async def test_compute_carrier_frequency_hom_corrected_method() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _StubFreqService(_ar_response())
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool(
        "compute_carrier_frequency",
        {
            "variant_id": "7-117559590-ATCT-A",
            "inheritance": "AR",
            "method": "hom_corrected",
        },
    )
    payload = result.structured_content or {}

    # nfe: (460 - 2*5) / (20000/2) = 450 / 10000 = 0.045
    by_pop = {row["population"]: row for row in payload["per_population"]}
    assert by_pop["nfe"]["carrier_frequency"] == pytest.approx(0.045, abs=1e-9)
    assert payload["method"] == "hom_corrected"


@pytest.mark.asyncio
async def test_compute_carrier_frequency_zero_an_yields_none_carrier() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    response = VariantFrequencyResponse(
        variant_id="7-117559590-ATCT-A",
        dataset="gnomad_r4",
        exome=VariantDataSource(
            ac=0,
            an=0,
            homozygote_count=0,
            populations=[PopulationFrequency(id="nfe", ac=0, an=0, homozygote_count=0)],
        ),
        genome=None,
    )
    service = _StubFreqService(response)
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool(
        "compute_carrier_frequency",
        {"variant_id": "7-117559590-ATCT-A", "inheritance": "AR"},
    )
    payload = result.structured_content or {}

    assert payload["overall"]["carrier_frequency"] is None
    assert payload["overall"]["ci_low"] is None
    assert payload["overall"]["ci_high"] is None


@pytest.mark.asyncio
async def test_compute_carrier_frequency_emits_citations_and_assumptions() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _StubFreqService(_ar_response())
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool(
        "compute_carrier_frequency",
        {"variant_id": "7-117559590-ATCT-A", "inheritance": "AR"},
    )
    payload = result.structured_content or {}

    assert any("Schrodi" in c for c in payload["citations"])
    assert "Hardy-Weinberg" in payload["assumptions_note"]
    assert payload["_meta"]["unsafe_for_clinical_use"] is True


@pytest.mark.asyncio
async def test_compute_carrier_frequency_emits_next_commands() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _StubFreqService(_ar_response())
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool(
        "compute_carrier_frequency",
        {"variant_id": "7-117559590-ATCT-A", "inheritance": "AR"},
    )
    payload = result.structured_content or {}

    next_tools = {cmd["tool"] for cmd in payload["_meta"]["next_commands"]}
    assert next_tools == {"get_clinvar_variant_details", "get_variant_frequencies"}
    # No self-reference.
    assert "compute_carrier_frequency" not in next_tools
```

- [ ] **Step 2: Run the tests, expect failure**

Run: `uv run pytest tests/unit/mcp/test_carrier_tool.py tests/unit/mcp/test_mcp_facade_surface.py::test_capabilities_tools_match_facade_tools`
Expected: FAIL — tool not registered; `call_tool("compute_carrier_frequency", ...)` raises an unknown-tool error and the parity test reports the tool only in `EXPECTED_TOOLS`/caps but not registered (or vice versa).

- [ ] **Step 3: Implement the tool module (AR path)**

Create `gnomad_link/mcp/tools/carrier.py`:

```python
"""Carrier-frequency tool: compute_carrier_frequency (pure local HWE math)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.build_check import detect_variant_id_mismatch
from gnomad_link.mcp.errors import BuildMismatchError, McpErrorContext, run_mcp_tool
from gnomad_link.mcp.schema_relax import relax_output_schema
from gnomad_link.models import VariantDataSource, VariantFrequencyResponse
from gnomad_link.services import FrequencyService
from gnomad_link.services.carrier_math import (
    ar_affected,
    ar_carrier,
    variant_carrier_rate,
    wilson_ci,
)

# Shared with get_variant_frequencies: autosomal CHROM-POS-REF-ALT grammar.
_AUTOSOMAL_VARIANT_ID_PATTERN = r"^([1-9]|1\d|2[0-2]|X|Y)-\d+-[ACGT]+-[ACGT]+$"

_CITATIONS = [
    "Schrodi et al. 2015, Hum Genet, doi:10.1007/s00439-015-1551-8 (2pq/q^2 carrier framework + CI concept)",
    "Karczewski et al. 2020, Nature (gnomAD allele-frequency reference)",
    "Guo et al. 2019; Zhu et al. 2022 (homozygote-corrected variant carrier rate)",
    "Hotakainen et al. 2025; Kandolin et al. 2024 (X-linked sex-split estimation)",
]

_ASSUMPTIONS_NOTE = (
    "Estimates assume Hardy-Weinberg equilibrium, random mating, complete "
    "penetrance, and a single causal variant. Frequencies are a minimum "
    "estimate from one gnomAD variant and are unsafe for clinical use."
)

_CARRIER_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "variant_id": {"type": "string"},
        "dataset": {"type": "string"},
        "inheritance": {"type": "string"},
        "method": {"type": "string"},
        "overall": {"type": ["object", "null"]},
        "per_population": {"type": "array", "items": {"type": "object"}},
        "summary": {"type": ["object", "null"]},
        "assumptions_note": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["variant_id", "dataset", "inheritance", "method"],
    "additionalProperties": True,
}


def _preferred_source(response: VariantFrequencyResponse) -> VariantDataSource | None:
    """Prefer exome (larger autosomal cohort), fall back to genome."""
    if response.exome is not None and response.exome.populations:
        return response.exome
    if response.genome is not None and response.genome.populations:
        return response.genome
    return response.exome or response.genome


def _ar_overall(source: VariantDataSource | None, method: str) -> dict[str, Any]:
    if source is None or source.an <= 0:
        return {
            "af": None,
            "carrier_frequency": None,
            "ci_low": None,
            "ci_high": None,
            "affected_frequency": None,
        }
    af = source.ac / source.an
    if method == "hom_corrected":
        cf = variant_carrier_rate(
            ac=source.ac, homozygote_count=source.homozygote_count, an=source.an
        )
    else:
        cf = ar_carrier(af)
    ci_low, ci_high = wilson_ci(af=af, n=source.an)
    return {
        "af": af,
        "carrier_frequency": cf,
        "ci_low": ar_carrier(ci_low) if ci_low is not None else None,
        "ci_high": ar_carrier(ci_high) if ci_high is not None else None,
        "affected_frequency": ar_affected(af),
    }


def _ar_per_population(source: VariantDataSource | None, method: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if source is None:
        return rows
    for pop in source.populations:
        if pop.allele_number <= 0:
            rows.append(
                {
                    "population": pop.name,
                    "ac": pop.allele_count,
                    "an": pop.allele_number,
                    "af": None,
                    "carrier_frequency": None,
                    "affected_frequency": None,
                }
            )
            continue
        af = pop.allele_count / pop.allele_number
        if method == "hom_corrected":
            cf = variant_carrier_rate(
                ac=pop.allele_count,
                homozygote_count=pop.homozygote_count,
                an=pop.allele_number,
            )
        else:
            cf = ar_carrier(af)
        rows.append(
            {
                "population": pop.name,
                "ac": pop.allele_count,
                "an": pop.allele_number,
                "af": af,
                "carrier_frequency": cf,
                "affected_frequency": ar_affected(af),
            }
        )
    return rows


def _max_carrier_population(rows: list[dict[str, Any]]) -> str | None:
    scored = [r for r in rows if r.get("carrier_frequency") is not None]
    if not scored:
        return None
    return max(scored, key=lambda r: r["carrier_frequency"])["population"]


def register_carrier_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="compute_carrier_frequency",
        title="Compute Carrier Frequency",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=relax_output_schema(_CARRIER_OUTPUT_SCHEMA),
        tags={"variant"},
    )
    async def compute_carrier_frequency(
        variant_id: Annotated[
            str,
            Field(
                description="CHROM-POS-REF-ALT (e.g. 7-117559590-ATCT-A). Autosomal/X-Y only.",
                min_length=5,
                max_length=200,
                pattern=_AUTOSOMAL_VARIANT_ID_PATTERN,
                examples=["7-117559590-ATCT-A", "X-153296777-C-T"],
            ),
        ],
        inheritance: Annotated[
            Literal["AR", "AD", "XL"],
            Field(
                description="AR=autosomal-recessive (2pq carrier, q^2 affected); AD=autosomal-dominant (1-(1-q)^2); XL=X-linked (sex-split).",
                examples=["AR"],
            ),
        ],
        dataset: Annotated[
            Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"],
            Field(
                description="gnomad_r4 (GRCh38, default, largest cohort), gnomad_r3 (GRCh38), gnomad_r2_1 (GRCh37 legacy)",
                examples=["gnomad_r4"],
            ),
        ] = "gnomad_r4",
        populations: Annotated[
            list[str] | None,
            Field(
                description="Restrict per_population rows to these population codes (e.g. ['afr','nfe']). None returns all.",
                examples=[["afr", "nfe"]],
            ),
        ] = None,
        method: Annotated[
            Literal["hwe", "hom_corrected"],
            Field(
                description="hwe = 2pq from AF; hom_corrected = (ac - 2*hom)/(an/2) observed variant carrier rate.",
                examples=["hwe"],
            ),
        ] = "hwe",
    ) -> dict[str, Any]:
        """Use this when a caller needs an estimated carrier/affected frequency derived from a single gnomAD allele frequency under Hardy-Weinberg assumptions for AR, AD, or X-linked inheritance. Pure local math on top of get_variant_frequencies; returns Wilson 95% CIs, per-population breakdown, and embedded citations. Estimates are research-use only, never clinical decision support. Returns ~2-4kB."""

        async def call() -> dict[str, Any]:
            inferred = detect_variant_id_mismatch(variant_id, dataset)
            if inferred is not None:
                raise BuildMismatchError(
                    variant_id=variant_id, inferred_build=inferred, dataset=dataset
                )
            service = service_factory()
            response = await service.get_variant_frequencies(variant_id, dataset)
            source = _preferred_source(response)
            overall = _ar_overall(source, method)
            per_population = _ar_per_population(source, method)
            if populations is not None:
                wanted = {p.lower() for p in populations}
                per_population = [
                    row for row in per_population if row["population"].lower() in wanted
                ]
            result: dict[str, Any] = {
                "variant_id": variant_id,
                "dataset": dataset,
                "inheritance": inheritance,
                "method": method,
                "overall": overall,
                "per_population": per_population,
                "summary": {
                    "max_carrier_frequency_population": _max_carrier_population(per_population)
                },
                "assumptions_note": _ASSUMPTIONS_NOTE,
                "citations": list(_CITATIONS),
            }
            reference_genome = "GRCh37" if dataset == "gnomad_r2_1" else "GRCh38"
            result["_meta"] = {
                "next_commands": [
                    {
                        "tool": "get_clinvar_variant_details",
                        "arguments": {
                            "variant_id": variant_id,
                            "reference_genome": reference_genome,
                        },
                    },
                    {
                        "tool": "get_variant_frequencies",
                        "arguments": {"variant_id": variant_id, "dataset": dataset},
                    },
                ]
            }
            return result

        return await run_mcp_tool(
            "compute_carrier_frequency",
            call,
            context=McpErrorContext(
                tool_name="compute_carrier_frequency",
                variant_id=variant_id,
                dataset=dataset,
            ),
        )
```

Wire it in `gnomad_link/mcp/tools/__init__.py` — add the import next to the other tool imports:

```python
from gnomad_link.mcp.tools.carrier import register_carrier_tools
```

and add the call line inside `register_gnomad_tools`, after `register_variant_tools`:

```python
    register_variant_tools(mcp, service_factory=service_factory)
    register_carrier_tools(mcp, service_factory=service_factory)
```

Append to capabilities in `gnomad_link/mcp/resources.py`. Add to the `tools` list (after `search_variants`, before `get_gnomad_diagnostics`):

```python
            "search_variants",
            "compute_carrier_frequency",
            "get_gnomad_diagnostics",
```

Add to `token_cost_hints` (keep value <=80 chars):

```python
            "search_variants": "~1-5kB (deprecated alias)",
            "compute_carrier_frequency": "~2-4kB (per-population dependent)",
            "get_gnomad_diagnostics": "<1kB",
```

Add to `tool_categories["variant"]`:

```python
            "variant": [
                "get_variant_frequencies",
                "get_variant_details",
                "get_mitochondrial_variant",
                "get_structural_variant",
                "compute_carrier_frequency",
            ],
```

- [ ] **Step 4: Run the tests, expect pass**

Run: `uv run pytest tests/unit/mcp/test_carrier_tool.py tests/unit/mcp/test_mcp_facade_surface.py`
Expected: PASS — AR tool tests green; `test_capabilities_tools_match_facade_tools`, `test_capabilities_resource_lists_token_cost_hints`, and `test_create_gnomad_mcp_exposes_expected_tool_names` all green with the new tool present in both registered tools and capabilities.

- [ ] **Step 5: Verify**

Run: `make ci-local`
Expected: PASS.

- [ ] **Step 6: Commit**

```
git add gnomad_link/mcp/tools/carrier.py gnomad_link/mcp/tools/__init__.py gnomad_link/mcp/resources.py tests/unit/mcp/test_mcp_facade_surface.py tests/unit/mcp/test_carrier_tool.py
git commit -m "feat(mcp): add compute_carrier_frequency tool (AR) with Wilson CIs and capabilities sync"
```

---

### Task C3.3: Extend compute_carrier_frequency to AD and XL (sex-split parsing) + tests

**Files:**
- Modify: `gnomad_link/mcp/tools/carrier.py`
- Modify: `tests/unit/mcp/test_carrier_tool.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/mcp/test_carrier_tool.py`:

```python
def _ad_response() -> VariantFrequencyResponse:
    # q = 0.011 (ac=220, an=20000).
    return VariantFrequencyResponse(
        variant_id="17-43044295-A-G",
        dataset="gnomad_r4",
        exome=VariantDataSource(
            ac=220,
            an=20000,
            homozygote_count=0,
            populations=[PopulationFrequency(id="nfe", ac=220, an=20000, homozygote_count=0)],
        ),
        genome=None,
        gene_symbol="BRCA1",
        major_consequence="missense_variant",
    )


def _xl_response() -> VariantFrequencyResponse:
    # Sex-split rows: XX (q_XX=0.01) and XY (q_XY=0.02), plus ancestry+sex rows.
    return VariantFrequencyResponse(
        variant_id="X-153296777-C-T",
        dataset="gnomad_r4",
        exome=VariantDataSource(
            ac=300,
            an=20000,
            homozygote_count=0,
            hemizygote_count=100,
            populations=[
                PopulationFrequency(id="XX", ac=100, an=10000, homozygote_count=0),
                PopulationFrequency(id="XY", ac=200, an=10000, homozygote_count=0),
                PopulationFrequency(id="nfe_XX", ac=60, an=6000, homozygote_count=0),
                PopulationFrequency(id="nfe_XY", ac=120, an=6000, homozygote_count=0),
            ],
        ),
        genome=None,
        gene_symbol="F8",
        major_consequence="missense_variant",
    )


@pytest.mark.asyncio
async def test_compute_carrier_frequency_ad_affected_or_carrier() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _StubFreqService(_ad_response())
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool(
        "compute_carrier_frequency",
        {"variant_id": "17-43044295-A-G", "inheritance": "AD"},
    )
    payload = result.structured_content or {}

    # AD overall: 1 - (1 - 0.011)^2 == 2*0.011 - 0.011^2 == 0.021879.
    assert payload["inheritance"] == "AD"
    assert payload["overall"]["affected_or_carrier_frequency"] == pytest.approx(
        0.021879, abs=1e-6
    )
    assert payload["overall"]["ci_low"] < payload["overall"]["affected_or_carrier_frequency"]
    assert payload["overall"]["ci_high"] > payload["overall"]["affected_or_carrier_frequency"]


@pytest.mark.asyncio
async def test_compute_carrier_frequency_xl_sex_split() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    service = _StubFreqService(_xl_response())
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool(
        "compute_carrier_frequency",
        {"variant_id": "X-153296777-C-T", "inheritance": "XL"},
    )
    payload = result.structured_content or {}

    assert payload["inheritance"] == "XL"
    # Overall q_XX = 0.01 -> female_carrier = 0.02, affected_female = 0.0001.
    assert payload["overall"]["female_carrier_frequency"] == pytest.approx(0.02, abs=1e-9)
    assert payload["overall"]["affected_female_frequency"] == pytest.approx(0.0001, abs=1e-9)
    # q_XY = 0.02 -> hemizygous affected male = 0.02 (no 2x, no square).
    assert payload["overall"]["affected_male_frequency"] == pytest.approx(0.02, abs=1e-9)
    # Ancestry rows are sex-split: nfe -> female_carrier from nfe_XX (q=0.01) = 0.02.
    by_pop = {row["population"]: row for row in payload["per_population"]}
    assert by_pop["nfe"]["female_carrier_frequency"] == pytest.approx(0.02, abs=1e-9)
    assert by_pop["nfe"]["affected_male_frequency"] == pytest.approx(0.02, abs=1e-9)


@pytest.mark.asyncio
async def test_compute_carrier_frequency_xl_missing_sex_rows_yields_none() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    response = VariantFrequencyResponse(
        variant_id="X-153296777-C-T",
        dataset="gnomad_r4",
        exome=VariantDataSource(
            ac=10,
            an=10000,
            homozygote_count=0,
            populations=[PopulationFrequency(id="nfe", ac=10, an=10000, homozygote_count=0)],
        ),
        genome=None,
    )
    service = _StubFreqService(response)
    mcp = create_gnomad_mcp(service_factory=lambda: service)
    result = await mcp.call_tool(
        "compute_carrier_frequency",
        {"variant_id": "X-153296777-C-T", "inheritance": "XL"},
    )
    payload = result.structured_content or {}

    # No XX/XY rows present -> sex-split estimates undefined, not zero.
    assert payload["overall"]["female_carrier_frequency"] is None
    assert payload["overall"]["affected_male_frequency"] is None
```

- [ ] **Step 2: Run the tests, expect failure**

Run: `uv run pytest tests/unit/mcp/test_carrier_tool.py`
Expected: FAIL — AD returns AR-shaped `overall` (no `affected_or_carrier_frequency`); XL returns AR-shaped `overall` (no `female_carrier_frequency`/`affected_male_frequency`).

- [ ] **Step 3: Implement AD + XL shaping in the tool module**

In `gnomad_link/mcp/tools/carrier.py`, extend the `carrier_math` import:

```python
from gnomad_link.services.carrier_math import (
    ad_affected_or_carrier,
    ar_affected,
    ar_carrier,
    variant_carrier_rate,
    wilson_ci,
    xl_affected_female,
    xl_affected_male,
    xl_female_carrier,
)
```

Add AD and XL builders below `_max_carrier_population`. The XL helpers read sex-encoded population ids (`XX`/`XY` for the overall split, and `<anc>_XX`/`<anc>_XY` per ancestry):

```python
def _ad_overall(source: VariantDataSource | None) -> dict[str, Any]:
    if source is None or source.an <= 0:
        return {
            "af": None,
            "affected_or_carrier_frequency": None,
            "ci_low": None,
            "ci_high": None,
        }
    af = source.ac / source.an
    ci_low, ci_high = wilson_ci(af=af, n=source.an)
    return {
        "af": af,
        "affected_or_carrier_frequency": ad_affected_or_carrier(af),
        "ci_low": ad_affected_or_carrier(ci_low) if ci_low is not None else None,
        "ci_high": ad_affected_or_carrier(ci_high) if ci_high is not None else None,
    }


def _ad_per_population(source: VariantDataSource | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if source is None:
        return rows
    for pop in source.populations:
        af = pop.allele_frequency
        rows.append(
            {
                "population": pop.name,
                "ac": pop.allele_count,
                "an": pop.allele_number,
                "af": af,
                "affected_or_carrier_frequency": (
                    ad_affected_or_carrier(af) if af is not None else None
                ),
                "carrier_frequency": ad_affected_or_carrier(af) if af is not None else None,
            }
        )
    return rows


def _sex_af(populations: list[PopulationFrequency], pop_id: str) -> float | None:
    for pop in populations:
        if pop.name == pop_id:
            return pop.allele_frequency
    return None


def _xl_block(q_xx: float | None, q_xy: float | None) -> dict[str, Any]:
    return {
        "q_xx": q_xx,
        "q_xy": q_xy,
        "female_carrier_frequency": xl_female_carrier(q_xx) if q_xx is not None else None,
        "affected_female_frequency": xl_affected_female(q_xx) if q_xx is not None else None,
        "affected_male_frequency": xl_affected_male(q_xy) if q_xy is not None else None,
    }


def _xl_ancestries(populations: list[PopulationFrequency]) -> list[str]:
    # Ancestry codes that carry sex-split rows like "<anc>_XX" / "<anc>_XY".
    ancestries: list[str] = []
    seen: set[str] = set()
    for pop in populations:
        name = pop.name
        if name in ("XX", "XY"):
            continue
        if name.endswith("_XX") or name.endswith("_XY"):
            anc = name.rsplit("_", 1)[0]
            if anc not in seen:
                seen.add(anc)
                ancestries.append(anc)
    return ancestries


def _xl_overall(source: VariantDataSource | None) -> dict[str, Any]:
    if source is None:
        return _xl_block(None, None)
    return _xl_block(
        _sex_af(source.populations, "XX"),
        _sex_af(source.populations, "XY"),
    )


def _xl_per_population(source: VariantDataSource | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if source is None:
        return rows
    for anc in _xl_ancestries(source.populations):
        q_xx = _sex_af(source.populations, f"{anc}_XX")
        q_xy = _sex_af(source.populations, f"{anc}_XY")
        block = _xl_block(q_xx, q_xy)
        rows.append(
            {
                "population": anc,
                "af_xx": q_xx,
                "af_xy": q_xy,
                "female_carrier_frequency": block["female_carrier_frequency"],
                "affected_female_frequency": block["affected_female_frequency"],
                "affected_male_frequency": block["affected_male_frequency"],
            }
        )
    return rows
```

For the `summary.max_carrier_frequency_population` to work across modes, update `_max_carrier_population` to read whichever carrier-style key the rows expose:

```python
def _max_carrier_population(rows: list[dict[str, Any]]) -> str | None:
    def _score(row: dict[str, Any]) -> float | None:
        for key in ("carrier_frequency", "female_carrier_frequency"):
            value = row.get(key)
            if value is not None:
                return value
        return None

    scored = [(row, _score(row)) for row in rows]
    scored = [(row, value) for row, value in scored if value is not None]
    if not scored:
        return None
    return max(scored, key=lambda item: item[1])[0]["population"]
```

Then branch in `call()` so the `overall`/`per_population` blocks match the inheritance mode. Replace the AR-only assignment with:

```python
            source = _preferred_source(response)
            if inheritance == "AD":
                overall = _ad_overall(source)
                per_population = _ad_per_population(source)
            elif inheritance == "XL":
                overall = _xl_overall(source)
                per_population = _xl_per_population(source)
            else:  # AR
                overall = _ar_overall(source, method)
                per_population = _ar_per_population(source, method)
```

The `populations` filter, `summary`, `assumptions_note`, `citations`, and `_meta.next_commands` block stay unchanged below the branch (the filter keys on `row["population"]`, which every mode emits).

- [ ] **Step 4: Run the tests, expect pass**

Run: `uv run pytest tests/unit/mcp/test_carrier_tool.py`
Expected: PASS — all AR, AD, and XL tests green, including missing-sex-row None handling.

- [ ] **Step 5: Verify**

Run: `make ci-local`
Expected: PASS (lint-loc confirms both `carrier.py` and `carrier_math.py` remain under 600 LOC).

- [ ] **Step 6: Commit**

```
git add gnomad_link/mcp/tools/carrier.py tests/unit/mcp/test_carrier_tool.py
git commit -m "feat(mcp): extend compute_carrier_frequency to AD and X-linked sex-split estimates"
```

---

## Phase C4: get_gene_summary — one-shot gene dossier (constraint + MANE + pathogenic ClinVar + best-effort GRCh37 expression)

This phase adds a single read-only MCP tool, `get_gene_summary`, that returns a compact gene "dossier" in one call: identity + coordinates, gnomAD constraint, canonical transcript, MANE-Select transcript, a ranked top-pathogenic ClinVar block, and a best-effort expression block (mean pext + top GTEx tissues) fetched from the GRCh37 dataset because expression is empty on GRCh38. ClinVar and expression are best-effort: a failure in either degrades to a `partial`/`unavailable` marker and never fails the whole call.

All new shaping lives in a NEW `gnomad_link/mcp/gene_summary_shaping.py` (never `shaping.py`, which is at 574 LOC). Orchestration lives in a NEW `gnomad_link/services/gene_summary_service.py` (never `frequency_service.py`, which is at 484 LOC). `FrequencyService` gains only a thin delegating `get_gene_summary` method.

**Files**

- Create: `gnomad_link/graphql/queries/common/gene_summary.graphql`
- Create: `gnomad_link/graphql/queries/common/transcript_gtex.graphql` (GTEx-only transcript query, C4.3)
- Modify: `gnomad_link/api/client.py` (add `get_gene_summary` + `get_transcript_gtex` client methods)
- Create: `gnomad_link/services/gene_summary_service.py` (new `GeneSummaryService`)
- Modify: `gnomad_link/services/frequency_service.py` (thin `get_gene_summary` delegate)
- Create: `gnomad_link/mcp/gene_summary_shaping.py` (`rank_pathogenic_clinvar`, `compact_expression`)
- Create: `gnomad_link/mcp/tools/gene_summary.py` (`register_gene_summary_tools`)
- Modify: `gnomad_link/mcp/tools/__init__.py` (one import + one call line)
- Modify: `gnomad_link/mcp/resources.py` (`tools`, `token_cost_hints`, `tool_categories`)
- Test: `tests/unit/graphql/test_gene_summary_query.py`
- Test: `tests/unit/services/test_gene_summary_service.py`
- Test: `tests/unit/mcp/test_gene_summary_shaping.py`
- Test: `tests/unit/mcp/test_gene_summary_tool.py`
- Modify: `tests/unit/mcp/test_mcp_facade_surface.py` (`EXPECTED_TOOLS`)
- Test: `tests/integration/test_gene_summary_expression_live.py`

---

### Task C4.1: gene_summary GraphQL document + client method + GeneSummaryService (gene + MANE + ClinVar fetch)

**Files:**
- Create: `gnomad_link/graphql/queries/common/gene_summary.graphql`
- Modify: `gnomad_link/api/client.py`
- Create: `gnomad_link/services/gene_summary_service.py`
- Modify: `gnomad_link/services/frequency_service.py`
- Test: `tests/unit/graphql/test_gene_summary_query.py`
- Test: `tests/unit/services/test_gene_summary_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/graphql/test_gene_summary_query.py`:

```python
from __future__ import annotations

from gnomad_link.graphql.query_loader import QueryLoader


def test_gene_summary_query_loads_and_resolves_constraint_fragment() -> None:
    loaded = QueryLoader().load_query("gene_summary", "v4")
    # Query head
    assert "query gene_summary(" in loaded
    assert "$gene_symbol: String" in loaded
    assert "$gene_id: String" in loaded
    assert "$reference_genome: ReferenceGenomeId!" in loaded
    # Identity + coordinates
    for field in ("gene_id", "symbol", "name", "chrom", "start", "stop"):
        assert field in loaded
    # Constraint + canonical + MANE
    assert "gnomad_constraint" in loaded
    assert "canonical_transcript_id" in loaded
    assert "mane_select_transcript" in loaded
    assert "refseq_id" in loaded
    # ClinVar variants (no args -> no 100kb cap)
    assert "clinvar_variants {" in loaded
    assert "clinical_significance" in loaded
    assert "gold_stars" in loaded
    # Expression scaffolding (populated on GRCh37, empty on GRCh38)
    assert "pext {" in loaded
    # The GeneConstraintFields fragment must have been inlined.
    assert "fragment GeneConstraintFields on GnomadConstraint" in loaded
    assert "#import" not in loaded
```

Create `tests/unit/services/test_gene_summary_service.py`:

```python
from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.services.gene_summary_service import GeneSummaryService


class _FakeClient:
    def __init__(self, gene_payload: dict[str, Any]) -> None:
        self.gene_payload = gene_payload
        self.calls: list[dict[str, Any]] = []

    async def get_gene_summary(
        self,
        *,
        gene_id: str | None,
        gene_symbol: str | None,
        reference_genome: str,
        dataset: str,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "gene_id": gene_id,
                "gene_symbol": gene_symbol,
                "reference_genome": reference_genome,
                "dataset": dataset,
            }
        )
        return {"gene": self.gene_payload}


def _gene_payload() -> dict[str, Any]:
    return {
        "gene_id": "ENSG00000169174",
        "symbol": "PCSK9",
        "name": "proprotein convertase subtilisin/kexin type 9",
        "chrom": "1",
        "start": 55039447,
        "stop": 55064852,
        "canonical_transcript_id": "ENST00000302118",
        "gnomad_constraint": {"pli": 0.01, "oe_lof": 0.8, "mis_z": 1.2},
        "mane_select_transcript": {
            "ensembl_id": "ENST00000302118",
            "ensembl_version": "5",
            "refseq_id": "NM_174936",
            "refseq_version": "4",
        },
        "clinvar_variants": [
            {"variant_id": "1-55039974-G-T", "clinical_significance": "Pathogenic", "gold_stars": 2},
        ],
        "pext": {"flags": [], "regions": []},
    }


@pytest.mark.asyncio
async def test_get_gene_summary_returns_gene_block_on_dataset_genome() -> None:
    client = _FakeClient(_gene_payload())
    svc = GeneSummaryService(client=client)

    result = await svc.get_gene_summary(
        gene_id="ENSG00000169174",
        gene_symbol=None,
        dataset="gnomad_r4",
    )

    assert result["gene_id"] == "ENSG00000169174"
    assert result["symbol"] == "PCSK9"
    assert result["coords"] == {"chrom": "1", "start": 55039447, "stop": 55064852}
    assert result["dataset"] == "gnomad_r4"
    assert result["constraint"]["pli"] == 0.01
    assert result["canonical_transcript_id"] == "ENST00000302118"
    assert result["mane_select_transcript"]["refseq_id"] == "NM_174936"
    assert result["clinvar_variants"][0]["variant_id"] == "1-55039974-G-T"
    # gnomad_r4 -> GRCh38 reference genome for the primary fetch.
    assert client.calls[0]["reference_genome"] == "GRCh38"


@pytest.mark.asyncio
async def test_get_gene_summary_uses_grch37_for_r2_1_dataset() -> None:
    client = _FakeClient(_gene_payload())
    svc = GeneSummaryService(client=client)

    await svc.get_gene_summary(gene_id="ENSG00000169174", gene_symbol=None, dataset="gnomad_r2_1")

    assert client.calls[0]["reference_genome"] == "GRCh37"


@pytest.mark.asyncio
async def test_get_gene_summary_clinvar_failure_sets_partial_flag() -> None:
    payload = _gene_payload()
    # A clinvar_variants value the shaper cannot iterate triggers the best-effort guard.
    payload["clinvar_variants"] = {"unexpected": "shape"}
    client = _FakeClient(payload)
    svc = GeneSummaryService(client=client)

    result = await svc.get_gene_summary(
        gene_id="ENSG00000169174", gene_symbol=None, dataset="gnomad_r4"
    )

    assert result["partial"] is True
    assert result["clinvar_variants"] == []
```

- [ ] **Step 2: Run the failing tests**

Run: `uv run pytest tests/unit/graphql/test_gene_summary_query.py tests/unit/services/test_gene_summary_service.py -q`
Expected: FAIL — `gene_summary.graphql` is missing (FileNotFoundError) and `gnomad_link.services.gene_summary_service` does not exist (ImportError).

- [ ] **Step 3: Create the GraphQL document**

Create `gnomad_link/graphql/queries/common/gene_summary.graphql`:

```graphql
#import "fragments.graphql"

query gene_summary($gene_symbol: String, $gene_id: String, $reference_genome: ReferenceGenomeId!) {
    gene(gene_symbol: $gene_symbol, gene_id: $gene_id, reference_genome: $reference_genome) {
        gene_id
        symbol
        name
        chrom
        start
        stop
        strand
        canonical_transcript_id
        mane_select_transcript {
            ensembl_id
            ensembl_version
            refseq_id
            refseq_version
        }
        gnomad_constraint {
            ...GeneConstraintFields
        }
        clinvar_variants {
            variant_id
            clinical_significance
            gold_stars
            major_consequence
            review_status
            hgvsc
            hgvsp
        }
        pext {
            flags
            regions {
                start
                stop
                mean
            }
        }
        flags
    }
}
```

Note: the loader resolves `#import "fragments.graphql"` by inlining only the `...GeneConstraintFields` fragment it detects (see `QueryLoader._resolve_fragments`). `clinvar_variants` takes no positional arguments on `Gene`, so it is not subject to the 100 kb region cap.

- [ ] **Step 4: Add the client method**

In `gnomad_link/api/client.py`, add a `get_gene_summary` method to `UnifiedGnomadClient`, mirroring the existing `get_gene` style (version from dataset, `process_variables` to inject `reference_genome`, then `execute_query`). Add it directly after `get_gene` (ends at line 63):

```python
    async def get_gene_summary(
        self,
        *,
        gene_id: str | None = None,
        gene_symbol: str | None = None,
        reference_genome: str | None = None,
        dataset: str | None = None,
    ) -> dict[str, Any]:
        """Get the gene-summary payload (constraint + MANE + clinvar_variants + pext).

        Args:
            gene_id: Ensembl gene ID
            gene_symbol: Gene symbol
            reference_genome: Reference genome (optional, auto-determined from dataset)
            dataset: Dataset (optional, for version determination)

        Returns:
            Raw gene_summary query result keyed by "gene"
        """
        version = "v4"
        if dataset:
            version = QueryBuilder.get_version_for_dataset(dataset)

        variables: dict[str, Any] = {}
        if gene_id:
            variables["gene_id"] = gene_id
        if gene_symbol:
            variables["gene_symbol"] = gene_symbol
        if reference_genome:
            variables["reference_genome"] = reference_genome

        processed_vars = self.query_builder.process_variables("gene_summary", variables, version)
        return await self.execute_query("gene_summary", processed_vars, version)
```

`process_variables` only injects `reference_genome` for a known set of `query_type` names. `gene_summary` is not in that set, so pass `reference_genome` explicitly from the service (Step 5). The `execute_query` call still runs `process_variables("gene_summary", ...)` internally as a no-op pass-through, which is harmless.

- [ ] **Step 5: Create GeneSummaryService**

Create `gnomad_link/services/gene_summary_service.py`:

```python
"""Orchestration service for the get_gene_summary MCP tool.

Assembles a one-shot gene dossier from a single gene_summary GraphQL query:
identity + coordinates, gnomAD constraint, canonical transcript, MANE-Select
transcript, ClinVar variants, and a pext scaffold. The ClinVar block is
best-effort: a malformed upstream shape degrades to an empty list with a
partial flag rather than failing the whole call. Expression (pext + GTEx) is
populated on GRCh37 and typically empty on GRCh38; the GRCh37 best-effort
expression fetch lands in Task C4.3.
"""

from __future__ import annotations

from typing import Any, Protocol


class _GeneSummaryClient(Protocol):
    async def get_gene_summary(
        self,
        *,
        gene_id: str | None,
        gene_symbol: str | None,
        reference_genome: str,
        dataset: str,
    ) -> dict[str, Any]: ...


def _dataset_reference_genome(dataset: str) -> str:
    """gnomad_r2_1 is GRCh37; gnomad_r3 / gnomad_r4 are GRCh38."""
    return "GRCh37" if dataset == "gnomad_r2_1" else "GRCh38"


class GeneSummaryService:
    """Assemble the gene_summary dossier from the unified gnomAD client."""

    def __init__(self, client: _GeneSummaryClient) -> None:
        self.client = client

    async def get_gene_summary(
        self,
        *,
        gene_id: str | None,
        gene_symbol: str | None,
        dataset: str = "gnomad_r4",
    ) -> dict[str, Any]:
        reference_genome = _dataset_reference_genome(dataset)
        raw = await self.client.get_gene_summary(
            gene_id=gene_id,
            gene_symbol=gene_symbol,
            reference_genome=reference_genome,
            dataset=dataset,
        )
        gene = raw.get("gene")
        if not gene:
            from gnomad_link.api.base_client import DataNotFoundError

            raise DataNotFoundError(
                f"Gene not found: gene_id={gene_id} gene_symbol={gene_symbol} in {dataset}"
            )

        partial = False
        raw_clinvar = gene.get("clinvar_variants")
        if isinstance(raw_clinvar, list):
            clinvar_variants = raw_clinvar
        else:
            clinvar_variants = []
            if raw_clinvar is not None:
                partial = True

        result: dict[str, Any] = {
            "gene_id": gene.get("gene_id"),
            "symbol": gene.get("symbol"),
            "name": gene.get("name"),
            "coords": {
                "chrom": gene.get("chrom"),
                "start": gene.get("start"),
                "stop": gene.get("stop"),
            },
            "dataset": dataset,
            "reference_genome": reference_genome,
            "constraint": gene.get("gnomad_constraint"),
            "canonical_transcript_id": gene.get("canonical_transcript_id"),
            "mane_select_transcript": gene.get("mane_select_transcript"),
            "clinvar_variants": clinvar_variants,
            "pext": gene.get("pext"),
            "flags": gene.get("flags") or [],
            "partial": partial,
        }
        return result
```

Export it from `gnomad_link/services/__init__.py`:

```python
"""Service layer for business logic."""

from .frequency_service import FrequencyService
from .gene_summary_service import GeneSummaryService

__all__ = [
    "FrequencyService",
    "GeneSummaryService",
]
```

- [ ] **Step 6: Add the thin FrequencyService delegate**

In `gnomad_link/services/frequency_service.py`, add a thin delegating method at the end of the "Thin pass-through wrappers" block (after `liftover_variant`, currently ending at line 484). This keeps tools calling `service.get_gene_summary(...)` and keeps the orchestration out of `frequency_service.py`:

```python
    async def get_gene_summary(
        self,
        *,
        gene_id: str | None = None,
        gene_symbol: str | None = None,
        dataset: str = "gnomad_r4",
    ) -> dict[str, Any]:
        """Delegate to GeneSummaryService for the one-shot gene dossier."""
        from gnomad_link.services.gene_summary_service import GeneSummaryService

        return await GeneSummaryService(client=self.client).get_gene_summary(
            gene_id=gene_id, gene_symbol=gene_symbol, dataset=dataset
        )
```

The import is function-local to avoid a module-level import cycle (`services/__init__` imports both modules) and to keep `frequency_service.py` from growing its import header. The whole addition is ~10 lines, keeping the file under the 600 cap.

- [ ] **Step 7: Run the tests**

Run: `uv run pytest tests/unit/graphql/test_gene_summary_query.py tests/unit/services/test_gene_summary_service.py -q`
Expected: PASS (5 tests).

- [ ] **Step 8: Full local CI gate**

Run: `make ci-local`
Expected: PASS (format, lint, `lint-loc`, typecheck, unit tests) — confirms the new query/client/service modules are under the LOC cap and type-clean before committing.

- [ ] **Step 9: Commit**

```
git add gnomad_link/graphql/queries/common/gene_summary.graphql gnomad_link/api/client.py gnomad_link/services/gene_summary_service.py gnomad_link/services/__init__.py gnomad_link/services/frequency_service.py tests/unit/graphql/test_gene_summary_query.py tests/unit/services/test_gene_summary_service.py
git commit -m "feat(mcp): add gene_summary query, client method, and GeneSummaryService dossier assembly"
```

---

### Task C4.2: gene_summary_shaping.py — ClinVar ranking/cap + expression compaction

**Files:**
- Create: `gnomad_link/mcp/gene_summary_shaping.py`
- Test: `tests/unit/mcp/test_gene_summary_shaping.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/mcp/test_gene_summary_shaping.py`:

```python
from __future__ import annotations

from gnomad_link.mcp.gene_summary_shaping import compact_expression, rank_pathogenic_clinvar


def test_rank_pathogenic_keeps_only_p_lp_sorted_by_gold_stars() -> None:
    rows = [
        {"variant_id": "1-1-A-G", "clinical_significance": "Benign", "gold_stars": 4},
        {"variant_id": "1-2-A-G", "clinical_significance": "Likely pathogenic", "gold_stars": 1},
        {"variant_id": "1-3-A-G", "clinical_significance": "Pathogenic", "gold_stars": 3},
        {"variant_id": "1-4-A-G", "clinical_significance": "Uncertain significance", "gold_stars": 2},
        {"variant_id": "1-5-A-G", "clinical_significance": "Pathogenic/Likely pathogenic", "gold_stars": 2},
    ]

    summary = rank_pathogenic_clinvar(rows, clinvar_limit=10)

    assert summary["pathogenic_count"] == 3
    # Highest gold_stars first; only P / LP rows survive.
    assert [r["variant_id"] for r in summary["top_pathogenic"]] == [
        "1-3-A-G",
        "1-5-A-G",
        "1-2-A-G",
    ]
    # Compact rows expose only the four advertised keys.
    assert set(summary["top_pathogenic"][0]) == {
        "variant_id",
        "clinical_significance",
        "gold_stars",
        "major_consequence",
    }
    assert "truncated" not in summary


def test_rank_pathogenic_emits_truncated_when_capped() -> None:
    rows = [
        {"variant_id": f"1-{i}-A-G", "clinical_significance": "Pathogenic", "gold_stars": i}
        for i in range(20)
    ]

    summary = rank_pathogenic_clinvar(rows, clinvar_limit=5)

    assert summary["pathogenic_count"] == 20
    assert len(summary["top_pathogenic"]) == 5
    # Top of the list is the highest gold_stars (19).
    assert summary["top_pathogenic"][0]["variant_id"] == "1-19-A-G"
    assert summary["truncated"] == {
        "kind": "pathogenic_clinvar",
        "dropped": 15,
        "filter": {"clinvar_limit": 5},
        "to_disable": "raise clinvar_limit (max 50) or response_mode='full'",
        "to_restore": "response_mode='full'",
    }


def test_rank_pathogenic_handles_missing_gold_stars() -> None:
    rows = [
        {"variant_id": "1-1-A-G", "clinical_significance": "Pathogenic", "gold_stars": None},
        {"variant_id": "1-2-A-G", "clinical_significance": "Pathogenic", "gold_stars": 1},
    ]

    summary = rank_pathogenic_clinvar(rows, clinvar_limit=10)

    # gold_stars=None ranks below an explicit star count.
    assert [r["variant_id"] for r in summary["top_pathogenic"]] == ["1-2-A-G", "1-1-A-G"]


def test_compact_expression_returns_mean_pext_and_top_tissues() -> None:
    pext = {
        "flags": [],
        "regions": [
            {"start": 1, "stop": 10, "mean": 0.8},
            {"start": 11, "stop": 20, "mean": 0.6},
        ],
    }
    gtex = [
        {"tissue": "Liver", "value": 50.0},
        {"tissue": "Brain", "value": 5.0},
        {"tissue": "Heart", "value": 30.0},
        {"tissue": "Lung", "value": 20.0},
        {"tissue": "Kidney", "value": 40.0},
        {"tissue": "Skin", "value": 1.0},
    ]

    expr = compact_expression(pext=pext, gtex_tissue_expression=gtex)

    assert expr["source_build"] == "GRCh37"
    assert expr["mean_pext"] == 0.7  # (0.8 + 0.6) / 2
    # Top 5 tissues by value, descending.
    assert [t["tissue"] for t in expr["top_tissues"]] == [
        "Liver",
        "Kidney",
        "Heart",
        "Lung",
        "Brain",
    ]
    assert "unavailable" not in expr


def test_compact_expression_unavailable_when_empty() -> None:
    expr = compact_expression(pext={"flags": [], "regions": []}, gtex_tissue_expression=[])

    assert expr["unavailable"] is True
    assert "GRCh38" in expr["note"]
```

- [ ] **Step 2: Run the failing tests**

Run: `uv run pytest tests/unit/mcp/test_gene_summary_shaping.py -q`
Expected: FAIL — `gnomad_link.mcp.gene_summary_shaping` does not exist (ImportError).

- [ ] **Step 3: Create the shaping module**

Create `gnomad_link/mcp/gene_summary_shaping.py`:

```python
"""Pure helpers that compact GeneSummaryService payloads for get_gene_summary.

Kept out of shaping.py (at its LOC ceiling). Mirrors the conventions in
shaping.py: stable sorts, self-describing ``truncated`` blocks with
``to_disable``/``to_restore`` hints, and compact row projection.
"""

from __future__ import annotations

from typing import Any

# Keys advertised in the compact top_pathogenic block.
_PATHOGENIC_ROW_KEEP = ("variant_id", "clinical_significance", "gold_stars", "major_consequence")


def _is_pathogenic(significance: str | None) -> bool:
    """True for ClinVar Pathogenic / Likely pathogenic (and combined) classifications."""
    if not significance:
        return False
    return "pathogenic" in significance.lower()


def _project_pathogenic_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: row.get(k) for k in _PATHOGENIC_ROW_KEEP}


def rank_pathogenic_clinvar(
    clinvar_variants: list[dict[str, Any]], *, clinvar_limit: int
) -> dict[str, Any]:
    """Filter to P/LP rows, sort by gold_stars desc, cap at clinvar_limit.

    Returns a block with ``pathogenic_count`` (total P/LP before the cap),
    ``top_pathogenic`` (capped, compact rows), and a self-describing
    ``truncated`` block when the cap drops rows. ``gold_stars`` of None ranks
    below any explicit star count; ties preserve original order.
    """
    pathogenic = [r for r in clinvar_variants if _is_pathogenic(r.get("clinical_significance"))]
    ranked = sorted(
        enumerate(pathogenic),
        key=lambda item: (-(item[1].get("gold_stars") or 0), item[0]),
    )
    ordered = [row for _, row in ranked]
    capped = ordered[:clinvar_limit]
    block: dict[str, Any] = {
        "pathogenic_count": len(pathogenic),
        "top_pathogenic": [_project_pathogenic_row(r) for r in capped],
    }
    if len(ordered) > clinvar_limit:
        block["truncated"] = {
            "kind": "pathogenic_clinvar",
            "dropped": len(ordered) - clinvar_limit,
            "filter": {"clinvar_limit": clinvar_limit},
            "to_disable": "raise clinvar_limit (max 50) or response_mode='full'",
            "to_restore": "response_mode='full'",
        }
    return block


def _mean_pext(pext: dict[str, Any] | None) -> float | None:
    if not pext:
        return None
    regions = pext.get("regions") or []
    means = [r.get("mean") for r in regions if r.get("mean") is not None]
    if not means:
        return None
    return round(sum(means) / len(means), 4)


def compact_expression(
    *,
    pext: dict[str, Any] | None,
    gtex_tissue_expression: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Compact expression: mean pext + top-5 GTEx tissues, sourced from GRCh37.

    Returns ``{"unavailable": True, "note": ...}`` when neither pext regions
    nor GTEx tissue values are present (the typical GRCh38 case).
    """
    mean_pext = _mean_pext(pext)
    tissues = [t for t in (gtex_tissue_expression or []) if t.get("value") is not None]
    if mean_pext is None and not tissues:
        return {
            "unavailable": True,
            "note": (
                "Expression (pext/GTEx) is empty for this gene; gnomAD populates "
                "it on GRCh37 (gnomad_r2_1) and typically not on GRCh38."
            ),
        }
    top_tissues = sorted(tissues, key=lambda t: t.get("value") or 0.0, reverse=True)[:5]
    return {
        "source_build": "GRCh37",
        "mean_pext": mean_pext,
        "top_tissues": [{"tissue": t.get("tissue"), "value": t.get("value")} for t in top_tissues],
    }
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/unit/mcp/test_gene_summary_shaping.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Full local CI gate**

Run: `make ci-local`
Expected: PASS (format, lint, `lint-loc`, typecheck, unit tests).

- [ ] **Step 6: Commit**

```
git add gnomad_link/mcp/gene_summary_shaping.py tests/unit/mcp/test_gene_summary_shaping.py
git commit -m "feat(mcp): add gene_summary_shaping with pathogenic-ClinVar ranking and expression compaction"
```

---

### Task C4.3: Best-effort GRCh37 expression fetch wired into GeneSummaryService

Expression (`pext` + `Transcript.gtex_tissue_expression`) is populated on GRCh37 (`gnomad_r2_1`) and typically empty on GRCh38. When the primary dataset is a GRCh38 build, the service does a second best-effort GRCh37 gene fetch to populate `pext`. GTEx tissue values for the canonical transcript come from a NEW dedicated query `transcript_gtex.graphql` and a NEW client method `get_transcript_gtex` — the existing `get_transcript` query does NOT select `gtex_tissue_expression` (verified: zero matches across `queries/v2,v3,v4`), so a dedicated selection is required. A failure in either fetch degrades to `expression: {unavailable: True, ...}` and never fails the call.

**Files:**
- Create: `gnomad_link/graphql/queries/common/transcript_gtex.graphql` (new GTEx-only transcript query)
- Modify: `gnomad_link/api/client.py` (add `get_transcript_gtex` client method)
- Modify: `gnomad_link/services/gene_summary_service.py`
- Test: `tests/unit/services/test_gene_summary_service.py` (extend)
- Test: `tests/integration/test_gene_summary_expression_live.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/services/test_gene_summary_service.py`:

```python
class _ExpressionClient:
    """Captures the GRCh37 fallback fetch and returns canned pext / GTEx."""

    def __init__(
        self,
        primary: dict[str, Any],
        grch37: dict[str, Any] | None = None,
        gtex: list[dict[str, Any]] | None = None,
        raise_grch37: bool = False,
    ) -> None:
        self.primary = primary
        self.grch37 = grch37
        self.gtex = gtex
        self.raise_grch37 = raise_grch37
        self.gene_calls: list[str] = []
        self.transcript_calls: list[tuple[str, str]] = []

    async def get_gene_summary(
        self,
        *,
        gene_id: str | None,
        gene_symbol: str | None,
        reference_genome: str,
        dataset: str,
    ) -> dict[str, Any]:
        self.gene_calls.append(reference_genome)
        if reference_genome == "GRCh37":
            if self.raise_grch37:
                raise RuntimeError("upstream GRCh37 fetch failed")
            return {"gene": self.grch37}
        return {"gene": self.primary}

    async def get_transcript_gtex(
        self, transcript_id: str, reference_genome: str = "GRCh37"
    ) -> dict[str, Any]:
        self.transcript_calls.append((transcript_id, reference_genome))
        return {"transcript": {"gtex_tissue_expression": self.gtex or []}}


def _grch37_gene_with_pext() -> dict[str, Any]:
    g = _gene_payload()
    g["pext"] = {"flags": [], "regions": [{"start": 1, "stop": 10, "mean": 0.9}]}
    return g


@pytest.mark.asyncio
async def test_expression_fetched_from_grch37_when_dataset_is_grch38() -> None:
    primary = _gene_payload()  # GRCh38 -> empty pext
    client = _ExpressionClient(
        primary=primary,
        grch37=_grch37_gene_with_pext(),
        gtex=[{"tissue": "Liver", "value": 42.0}],
    )
    svc = GeneSummaryService(client=client)

    result = await svc.get_gene_summary(
        gene_id="ENSG00000169174", gene_symbol=None, dataset="gnomad_r4", include_expression=True
    )

    assert client.gene_calls == ["GRCh38", "GRCh37"]
    assert result["expression"]["source_build"] == "GRCh37"
    assert result["expression"]["mean_pext"] == 0.9
    assert result["expression"]["top_tissues"][0]["tissue"] == "Liver"


@pytest.mark.asyncio
async def test_expression_skipped_when_include_expression_false() -> None:
    client = _ExpressionClient(primary=_gene_payload())
    svc = GeneSummaryService(client=client)

    result = await svc.get_gene_summary(
        gene_id="ENSG00000169174", gene_symbol=None, dataset="gnomad_r4", include_expression=False
    )

    assert client.gene_calls == ["GRCh38"]
    assert "expression" not in result


@pytest.mark.asyncio
async def test_expression_failure_degrades_to_unavailable_and_sets_partial() -> None:
    client = _ExpressionClient(primary=_gene_payload(), raise_grch37=True)
    svc = GeneSummaryService(client=client)

    result = await svc.get_gene_summary(
        gene_id="ENSG00000169174", gene_symbol=None, dataset="gnomad_r4", include_expression=True
    )

    assert result["expression"]["unavailable"] is True
    assert result["partial"] is True
```

Create `tests/integration/test_gene_summary_expression_live.py`:

```python
"""Live expression-population check for get_gene_summary. Gated by `integration`."""

from __future__ import annotations

import pytest

from gnomad_link.api.client import UnifiedGnomadClient
from gnomad_link.services.gene_summary_service import GeneSummaryService

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_pcsk9_expression_populated_from_grch37_not_grch38() -> None:
    client = UnifiedGnomadClient()
    try:
        svc = GeneSummaryService(client=client)
        result = await svc.get_gene_summary(
            gene_id="ENSG00000169174",
            gene_symbol=None,
            dataset="gnomad_r4",
            include_expression=True,
        )
    finally:
        await client.close()

    expr = result["expression"]
    # GRCh38 pext is empty upstream; the service backfills from GRCh37.
    assert expr.get("source_build") == "GRCh37"
    assert expr.get("mean_pext") is not None
    assert len(expr.get("top_tissues") or []) >= 1


@pytest.mark.asyncio
async def test_grch38_gene_pext_is_empty_directly() -> None:
    client = UnifiedGnomadClient()
    try:
        raw = await client.get_gene_summary(
            gene_id="ENSG00000169174",
            gene_symbol=None,
            reference_genome="GRCh38",
            dataset="gnomad_r4",
        )
    finally:
        await client.close()

    gene = raw["gene"]
    regions = (gene.get("pext") or {}).get("regions") or []
    assert regions == [], "GRCh38 pext expected empty; expression must come from GRCh37"
```

- [ ] **Step 2: Run the failing unit tests**

Run: `uv run pytest tests/unit/services/test_gene_summary_service.py -q`
Expected: FAIL — `get_gene_summary` does not accept `include_expression`, and no `expression` block is produced.

- [ ] **Step 3: Implement the best-effort expression fetch**

Edit `gnomad_link/services/gene_summary_service.py`. Widen the `_GeneSummaryClient` Protocol to include `get_transcript`, add `include_expression` to the signature, and append the best-effort block. Replace the Protocol and add a private helper plus the new parameter:

```python
class _GeneSummaryClient(Protocol):
    async def get_gene_summary(
        self,
        *,
        gene_id: str | None,
        gene_symbol: str | None,
        reference_genome: str,
        dataset: str,
    ) -> dict[str, Any]: ...

    async def get_transcript_gtex(
        self, transcript_id: str, reference_genome: str = "GRCh37"
    ) -> dict[str, Any]: ...
```

Add the import at the top of the module:

```python
from gnomad_link.mcp.gene_summary_shaping import compact_expression
```

First create the dedicated GTEx transcript query `gnomad_link/graphql/queries/common/transcript_gtex.graphql` (the existing `transcript` query does not select GTEx):

```graphql
query transcript_gtex($transcript_id: String!, $reference_genome: ReferenceGenomeId!) {
    transcript(transcript_id: $transcript_id, reference_genome: $reference_genome) {
        transcript_id
        gtex_tissue_expression {
            tissue
            value
        }
    }
}
```

Then add the `get_transcript_gtex` client method to `UnifiedGnomadClient` in `gnomad_link/api/client.py`, mirroring the existing `get_transcript` style but loading the `transcript_gtex` document and passing `reference_genome` explicitly:

```python
    async def get_transcript_gtex(
        self, transcript_id: str, reference_genome: str = "GRCh37"
    ) -> dict[str, Any]:
        """Fetch only GTEx tissue expression for a transcript (GRCh37-populated)."""
        variables = {
            "transcript_id": transcript_id,
            "reference_genome": reference_genome,
        }
        return await self.execute_query("transcript_gtex", variables, "v2")
```

Change the public method signature to accept `include_expression: bool = True`, and after building `result` (before `return result`) add:

```python
        if include_expression:
            try:
                result["expression"] = await self._fetch_expression(
                    gene=gene,
                    gene_id=gene.get("gene_id") or gene_id,
                    gene_symbol=gene_symbol,
                    dataset=dataset,
                    reference_genome=reference_genome,
                )
            except Exception:
                # Best-effort: never fail the whole call on an expression error.
                result["expression"] = {
                    "unavailable": True,
                    "note": "Expression lookup failed upstream; gene data above is unaffected.",
                }
                result["partial"] = True
```

Add the private helper method to `GeneSummaryService`:

```python
    async def _fetch_expression(
        self,
        *,
        gene: dict[str, Any],
        gene_id: str | None,
        gene_symbol: str | None,
        dataset: str,
        reference_genome: str,
    ) -> dict[str, Any]:
        """Resolve pext + canonical-transcript GTEx, backfilling from GRCh37 when needed.

        On GRCh38 the primary gene's pext is empty, so re-fetch the gene on
        GRCh37 (gnomad_r2_1) to obtain populated pext and the canonical
        transcript GTEx expression. compact_expression downgrades to
        {"unavailable": True} when both are empty.
        """
        pext = gene.get("pext")
        canonical_id = gene.get("canonical_transcript_id")
        if reference_genome == "GRCh37":
            gtex = await self._canonical_gtex(canonical_id, "GRCh37")
            return compact_expression(pext=pext, gtex_tissue_expression=gtex)

        # GRCh38 primary: backfill from GRCh37.
        raw37 = await self.client.get_gene_summary(
            gene_id=gene_id,
            gene_symbol=gene_symbol,
            reference_genome="GRCh37",
            dataset="gnomad_r2_1",
        )
        gene37 = raw37.get("gene") or {}
        pext37 = gene37.get("pext")
        canonical37 = gene37.get("canonical_transcript_id") or canonical_id
        gtex37 = await self._canonical_gtex(canonical37, "GRCh37")
        return compact_expression(pext=pext37, gtex_tissue_expression=gtex37)

    async def _canonical_gtex(
        self, transcript_id: str | None, reference_genome: str
    ) -> list[dict[str, Any]]:
        if not transcript_id:
            return []
        raw = await self.client.get_transcript_gtex(transcript_id, reference_genome)
        transcript = raw.get("transcript") or {}
        return list(transcript.get("gtex_tissue_expression") or [])
```

Note the `from gnomad_link.mcp.gene_summary_shaping import compact_expression` module-level import is safe: `gene_summary_shaping` imports only `typing`, so there is no cycle back into `services`.

- [ ] **Step 4: Run the unit tests**

Run: `uv run pytest tests/unit/services/test_gene_summary_service.py -q`
Expected: PASS (8 tests). The integration test is collected but skipped under the default `make test` run (no `integration` marker selected).

- [ ] **Step 5: Verify the integration test is collected under the marker only**

Run: `uv run pytest tests/integration/test_gene_summary_expression_live.py --collect-only -q`
Expected: 2 tests collected, both carrying the `integration` marker (they only execute under `make test-integration`).

- [ ] **Step 6: Full local CI gate**

Run: `make ci-local`
Expected: PASS (format, lint, `lint-loc`, typecheck, unit tests). The `integration`-marked live test is not selected by the default run.

- [ ] **Step 7: Commit**

```
git add gnomad_link/graphql/queries/common/transcript_gtex.graphql gnomad_link/api/client.py gnomad_link/services/gene_summary_service.py tests/unit/services/test_gene_summary_service.py tests/integration/test_gene_summary_expression_live.py
git commit -m "feat(mcp): best-effort GRCh37 expression backfill in GeneSummaryService"
```

---

### Task C4.4: get_gene_summary MCP tool + capabilities/parity sync + tool test

**Files:**
- Create: `gnomad_link/mcp/tools/gene_summary.py`
- Modify: `gnomad_link/mcp/tools/__init__.py`
- Modify: `gnomad_link/mcp/resources.py`
- Test: `tests/unit/mcp/test_gene_summary_tool.py`
- Modify: `tests/unit/mcp/test_mcp_facade_surface.py`

- [ ] **Step 1: Write failing tests**

Add `"get_gene_summary"` to the `EXPECTED_TOOLS` set in `tests/unit/mcp/test_mcp_facade_surface.py` (this also flows into `EXPECTED_DATA_TOOLS` and locks the parity gate `test_capabilities_tools_match_facade_tools`):

```python
EXPECTED_TOOLS = {
    "get_server_capabilities",
    "get_variant_frequencies",
    "get_variant_details",
    "get_gene_details",
    "get_gene_variants",
    "get_gene_summary",
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
    "get_gnomad_diagnostics",
}
```

Create `tests/unit/mcp/test_gene_summary_tool.py`:

```python
from __future__ import annotations

from typing import Any

import pytest

from gnomad_link.mcp.facade import create_gnomad_mcp


class _StubGeneSummaryService:
    """Stub FrequencyService exposing only get_gene_summary."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def get_gene_summary(
        self,
        *,
        gene_id: str | None = None,
        gene_symbol: str | None = None,
        dataset: str = "gnomad_r4",
    ) -> dict[str, Any]:
        self.calls.append(
            {"gene_id": gene_id, "gene_symbol": gene_symbol, "dataset": dataset}
        )
        return {
            "gene_id": "ENSG00000169174",
            "symbol": "PCSK9",
            "name": "proprotein convertase subtilisin/kexin type 9",
            "coords": {"chrom": "1", "start": 55039447, "stop": 55064852},
            "dataset": dataset,
            "reference_genome": "GRCh38",
            "constraint": {"pli": 0.01, "oe_lof": 0.8},
            "canonical_transcript_id": "ENST00000302118",
            "mane_select_transcript": {"ensembl_id": "ENST00000302118", "refseq_id": "NM_174936"},
            "clinvar_variants": [
                {"variant_id": "1-1-A-G", "clinical_significance": "Pathogenic", "gold_stars": 3,
                 "major_consequence": "missense_variant"},
                {"variant_id": "1-2-A-G", "clinical_significance": "Likely pathogenic", "gold_stars": 1,
                 "major_consequence": "missense_variant"},
                {"variant_id": "1-3-A-G", "clinical_significance": "Benign", "gold_stars": 2,
                 "major_consequence": "synonymous_variant"},
            ],
            "pext": {"flags": [], "regions": []},
            "expression": {"source_build": "GRCh37", "mean_pext": 0.7,
                           "top_tissues": [{"tissue": "Liver", "value": 42.0}]},
            "flags": [],
            "partial": False,
        }


@pytest.mark.asyncio
async def test_get_gene_summary_compact_shapes_clinvar_and_meta() -> None:
    stub = _StubGeneSummaryService()
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool("get_gene_summary", {"gene_symbol": "PCSK9"})
    payload = result.structured_content or {}

    assert payload["symbol"] == "PCSK9"
    assert payload["clinvar_summary"]["pathogenic_count"] == 2
    assert payload["clinvar_summary"]["top_pathogenic"][0]["variant_id"] == "1-1-A-G"
    # Compact mode replaces the raw clinvar_variants list with the ranked summary.
    assert "clinvar_variants" not in payload
    assert payload["expression"]["source_build"] == "GRCh37"
    # next_commands cross-link, capped at 3, no self-reference.
    next_cmds = payload["_meta"]["next_commands"]
    tools = [c["tool"] for c in next_cmds]
    assert tools == ["get_gene_variants", "get_clinvar_variant_details", "get_coverage"]
    assert "get_gene_summary" not in tools
    # Research-use meta injected by run_mcp_tool.
    assert payload["_meta"]["unsafe_for_clinical_use"] is True
    assert "gnomad_release" in payload["_meta"]
    assert stub.calls[0]["gene_symbol"] == "PCSK9"


@pytest.mark.asyncio
async def test_get_gene_summary_full_returns_raw_clinvar_variants() -> None:
    stub = _StubGeneSummaryService()
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "get_gene_summary", {"gene_symbol": "PCSK9", "response_mode": "full"}
    )
    payload = result.structured_content or {}

    assert isinstance(payload["clinvar_variants"], list)
    assert len(payload["clinvar_variants"]) == 3
    assert "clinvar_summary" not in payload


@pytest.mark.asyncio
async def test_get_gene_summary_requires_exactly_one_identifier() -> None:
    stub = _StubGeneSummaryService()
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    none_given = (await mcp.call_tool("get_gene_summary", {})).structured_content or {}
    assert none_given["error_code"] == "validation_failed"

    both_given = (
        await mcp.call_tool(
            "get_gene_summary",
            {"gene_symbol": "PCSK9", "gene_id": "ENSG00000169174"},
        )
    ).structured_content or {}
    assert both_given["error_code"] == "validation_failed"
    # Service is never invoked when identifier validation fails.
    assert stub.calls == []


@pytest.mark.asyncio
async def test_get_gene_summary_advertised_in_capabilities() -> None:
    from gnomad_link.mcp.resources import get_capabilities_resource

    caps = get_capabilities_resource()
    assert "get_gene_summary" in caps["tools"]
    assert "get_gene_summary" in caps["token_cost_hints"]
    assert len(caps["token_cost_hints"]["get_gene_summary"]) <= 80
    assert "get_gene_summary" in caps["tool_categories"]["gene"]
```

- [ ] **Step 2: Run the failing tests**

Run: `uv run pytest tests/unit/mcp/test_gene_summary_tool.py tests/unit/mcp/test_mcp_facade_surface.py -q`
Expected: FAIL — `get_gene_summary` is not registered (the tool test errors on an unknown tool, and `test_capabilities_tools_match_facade_tools` plus the new `EXPECTED_TOOLS` assertions fail).

- [ ] **Step 3: Create the tool module**

Create `gnomad_link/mcp/tools/gene_summary.py`:

```python
"""Gene summary tool: get_gene_summary (one-shot gene dossier)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool
from gnomad_link.mcp.gene_summary_shaping import rank_pathogenic_clinvar
from gnomad_link.mcp.schema_relax import relax_output_schema
from gnomad_link.services import FrequencyService

_GENE_SUMMARY_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "gene_id": {"type": ["string", "null"]},
        "symbol": {"type": ["string", "null"]},
        "name": {"type": ["string", "null"]},
        "coords": {"type": ["object", "null"]},
        "dataset": {"type": "string"},
        "constraint": {"type": ["object", "null"]},
        "canonical_transcript_id": {"type": ["string", "null"]},
        "mane_select_transcript": {"type": ["object", "null"]},
        "clinvar_summary": {"type": ["object", "null"]},
        "clinvar_variants": {"type": ["array", "null"], "items": {"type": "object"}},
        "expression": {"type": ["object", "null"]},
        "partial": {"type": "boolean"},
    },
    "required": ["dataset"],
    "additionalProperties": True,
}


def register_gene_summary_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="get_gene_summary",
        title="Get Gene Summary",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=relax_output_schema(_GENE_SUMMARY_OUTPUT_SCHEMA),
        tags={"gene"},
    )
    async def get_gene_summary(
        gene_symbol: Annotated[
            str | None,
            Field(description="HGNC gene symbol; provide this OR gene_id.", examples=["PCSK9"]),
        ] = None,
        gene_id: Annotated[
            str | None,
            Field(
                description="Ensembl gene ID; provide this OR gene_symbol.",
                examples=["ENSG00000169174"],
            ),
        ] = None,
        dataset: Annotated[
            Literal["gnomad_r2_1", "gnomad_r3", "gnomad_r4"],
            Field(
                description="gnomad_r4 (GRCh38, default), gnomad_r3 (GRCh38), gnomad_r2_1 (GRCh37 legacy)",
                examples=["gnomad_r4"],
            ),
        ] = "gnomad_r4",
        clinvar_limit: Annotated[
            int,
            Field(ge=1, le=50, description="Cap on top_pathogenic ClinVar rows in compact mode."),
        ] = 10,
        include_expression: Annotated[
            bool,
            Field(description="Include the best-effort GRCh37 expression block (pext + GTEx)."),
        ] = True,
        response_mode: Annotated[
            Literal["compact", "full"],
            Field(
                description=(
                    "compact ranks pathogenic ClinVar into clinvar_summary and trims expression; "
                    "full returns the raw clinvar_variants list and untrimmed expression."
                )
            ),
        ] = "compact",
    ) -> dict[str, Any]:
        """Use this when a caller wants a one-shot gene dossier: constraint (pLI/oe_lof), canonical and MANE-Select transcripts, top pathogenic ClinVar variants, and expression (pext + GTEx). Provide exactly one of gene_symbol/gene_id. Follow with get_gene_variants for per-variant rows. Returns compact ~3-8kB."""

        async def call() -> dict[str, Any]:
            if bool(gene_symbol) == bool(gene_id):
                raise ValueError("Provide exactly one of gene_symbol or gene_id.")
            service = service_factory()
            summary = await service.get_gene_summary(
                gene_id=gene_id,
                gene_symbol=gene_symbol,
                dataset=dataset,
            )

            result: dict[str, Any] = dict(summary)
            if not include_expression:
                result.pop("expression", None)
            if response_mode == "compact":
                raw_clinvar = result.pop("clinvar_variants", None) or []
                result["clinvar_summary"] = rank_pathogenic_clinvar(
                    raw_clinvar, clinvar_limit=clinvar_limit
                )

            resolved_id = result.get("gene_id") or gene_id
            existing_meta: dict[str, Any] = result.get("_meta") or {}
            existing_next: list[Any] = existing_meta.get("next_commands", [])
            next_commands: list[dict[str, Any]] = [
                {"tool": "get_gene_variants", "arguments": {"gene_id": resolved_id}},
                {
                    "tool": "get_clinvar_variant_details",
                    "arguments": {
                        "reference_genome": "GRCh37" if dataset == "gnomad_r2_1" else "GRCh38"
                    },
                },
                {"tool": "get_coverage", "arguments": {"gene_id": resolved_id}},
            ]
            result["_meta"] = {
                **existing_meta,
                "next_commands": [*existing_next, *next_commands][:3],
            }
            return result

        return await run_mcp_tool(
            "get_gene_summary",
            call,
            context=McpErrorContext(
                tool_name="get_gene_summary",
                gene_id=gene_id,
                gene_symbol=gene_symbol,
                dataset=dataset,
            ),
        )
```

- [ ] **Step 4: Wire registration**

In `gnomad_link/mcp/tools/__init__.py`, add the import alongside the others:

```python
from gnomad_link.mcp.tools.gene_summary import register_gene_summary_tools
```

and add the call line inside `register_gnomad_tools`, after `register_gene_tools(...)`:

```python
    register_gene_summary_tools(mcp, *, service_factory=service_factory)
```

(use the existing call style: `register_gene_summary_tools(mcp, service_factory=service_factory)`.)

- [ ] **Step 5: Sync capabilities in resources.py**

In `gnomad_link/mcp/resources.py`, add `"get_gene_summary"` to the `tools` list (after `"get_gene_variants"`):

```python
            "get_gene_variants",
            "get_gene_summary",
```

Add the `token_cost_hints` entry (<=80 chars), after the `get_gene_variants` hint:

```python
            "get_gene_variants": "~5-50kB (limit-dependent)",
            "get_gene_summary": "compact ~3-8kB, full up to ~40kB",
```

Add `"get_gene_summary"` to the `tool_categories["gene"]` list:

```python
            "gene": ["get_gene_details", "get_gene_variants", "get_gene_summary", "search_genes"],
```

- [ ] **Step 6: Run the focused tests**

Run: `uv run pytest tests/unit/mcp/test_gene_summary_tool.py tests/unit/mcp/test_mcp_facade_surface.py -q`
Expected: PASS — including `test_capabilities_tools_match_facade_tools`, `test_capabilities_resource_lists_token_cost_hints`, and the new `test_get_gene_summary_*` tests.

- [ ] **Step 7: Full local CI**

Run: `make ci-local`
Expected: PASS — format-check, lint, `lint-loc` (all new modules well under 600 LOC; `frequency_service.py` grew by ~10 lines and stays under the cap; `shaping.py` is untouched), typecheck, and the unit suite all green.

- [ ] **Step 8: Commit**

```
git add gnomad_link/mcp/tools/gene_summary.py gnomad_link/mcp/tools/__init__.py gnomad_link/mcp/resources.py tests/unit/mcp/test_gene_summary_tool.py tests/unit/mcp/test_mcp_facade_surface.py
git commit -m "feat(mcp): add get_gene_summary tool with compact dossier shaping and capabilities sync"

---

## Phase C5: search_structural_variants — list structural variants in a gene or region with client-side type/length filtering

This tool adds the first *list* surface for structural variants. SVs use a DISTINCT dataset enum (`StructuralVariantDatasetId`: `gnomad_sv_r4` => GRCh38, `gnomad_sv_r2_1` => GRCh37) — NOT the `gnomad_r2_1/r3/r4` `DatasetId` used by SNV/indel tools. SV `variant_id` values are opaque (e.g. `DEL_19_1`), NOT `CHROM-POS-REF-ALT`, so no SNV regex is applied. The upstream `gene.structural_variants` / `region.structural_variants` fields take NO filter arguments, so ALL filtering (`sv_type`, `min_length`, `max_length`) and the `limit` cap happen client-side. `next_commands` points to `get_structural_variant` for each returned opaque id.

**Files:**
- Create: `gnomad_link/graphql/queries/common/sv_search.graphql`
- Create: `gnomad_link/services/structural_variant_service.py`
- Create: `gnomad_link/mcp/sv_shaping.py`
- Create: `gnomad_link/mcp/tools/sv_search.py`
- Modify: `gnomad_link/api/client.py` (add `search_structural_variants_by_gene` + `search_structural_variants_by_region`)
- Modify: `gnomad_link/services/frequency_service.py` (add thin `search_structural_variants` delegating method)
- Modify: `gnomad_link/mcp/tools/__init__.py` (one import + one call line)
- Modify: `gnomad_link/mcp/resources.py` (`tools`, `token_cost_hints`, `tool_categories`)
- Test: `tests/unit/services/test_structural_variant_service.py`
- Test: `tests/unit/mcp/test_sv_shaping.py`
- Test: `tests/unit/mcp/test_sv_search_tool.py`
- Modify (test): `tests/unit/mcp/test_mcp_facade_surface.py` (`EXPECTED_TOOLS`)

---

### Task C5.1: GraphQL doc + client methods + StructuralVariantService (gene & region search)

**Files:**
- Create: `gnomad_link/graphql/queries/common/sv_search.graphql`
- Create: `gnomad_link/services/structural_variant_service.py`
- Modify: `gnomad_link/api/client.py`
- Modify: `gnomad_link/services/frequency_service.py`
- Create: `tests/unit/services/test_structural_variant_service.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/services/test_structural_variant_service.py`:

```python
"""Unit tests for StructuralVariantService gene/region SV search.

Offline: the gnomAD client is an AsyncMock; the service must shape the
nested GraphQL envelope ({"gene": {"structural_variants": [...]}} or
{"region": {"structural_variants": [...]}}) into a flat list of dicts.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from gnomad_link.services.structural_variant_service import StructuralVariantService

_SV_ROWS = [
    {
        "variant_id": "DEL_19_1",
        "type": "DEL",
        "chrom": "19",
        "pos": 11_089_000,
        "end": 11_133_820,
        "length": 44_820,
        "af": 0.0001,
        "ac": 3,
        "an": 30000,
        "major_consequence": "lof",
    },
    {
        "variant_id": "DUP_19_2",
        "type": "DUP",
        "chrom": "19",
        "pos": 11_100_000,
        "end": 11_200_000,
        "length": 100_000,
        "af": 0.002,
        "ac": 60,
        "an": 30000,
        "major_consequence": "copy_gain",
    },
]


@pytest.fixture
def service_with_client():
    client = AsyncMock()
    return StructuralVariantService(client=client), client


@pytest.mark.asyncio
async def test_search_by_gene_symbol_returns_flat_list(service_with_client) -> None:
    service, client = service_with_client
    client.search_structural_variants_by_gene.return_value = list(_SV_ROWS)

    rows = await service.search_structural_variants(
        gene_symbol="SMARCA4", sv_dataset="gnomad_sv_r4"
    )

    client.search_structural_variants_by_gene.assert_awaited_once_with(
        gene_id=None,
        gene_symbol="SMARCA4",
        reference_genome="GRCh38",
        sv_dataset="gnomad_sv_r4",
    )
    assert [r["variant_id"] for r in rows] == ["DEL_19_1", "DUP_19_2"]


@pytest.mark.asyncio
async def test_search_by_gene_id_uses_gene_id(service_with_client) -> None:
    service, client = service_with_client
    client.search_structural_variants_by_gene.return_value = list(_SV_ROWS)

    await service.search_structural_variants(
        gene_id="ENSG00000127616", sv_dataset="gnomad_sv_r4"
    )

    client.search_structural_variants_by_gene.assert_awaited_once_with(
        gene_id="ENSG00000127616",
        gene_symbol=None,
        reference_genome="GRCh38",
        sv_dataset="gnomad_sv_r4",
    )


@pytest.mark.asyncio
async def test_search_by_region_parses_and_delegates(service_with_client) -> None:
    service, client = service_with_client
    client.search_structural_variants_by_region.return_value = list(_SV_ROWS)

    rows = await service.search_structural_variants(
        region="19-11089000-11200000", sv_dataset="gnomad_sv_r4"
    )

    client.search_structural_variants_by_region.assert_awaited_once_with(
        chrom="19",
        start=11_089_000,
        stop=11_200_000,
        reference_genome="GRCh38",
        sv_dataset="gnomad_sv_r4",
    )
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_r2_1_maps_to_grch37(service_with_client) -> None:
    service, client = service_with_client
    client.search_structural_variants_by_gene.return_value = []

    await service.search_structural_variants(
        gene_symbol="SMARCA4", sv_dataset="gnomad_sv_r2_1"
    )

    client.search_structural_variants_by_gene.assert_awaited_once_with(
        gene_id=None,
        gene_symbol="SMARCA4",
        reference_genome="GRCh37",
        sv_dataset="gnomad_sv_r2_1",
    )


@pytest.mark.asyncio
async def test_requires_exactly_one_entry_argument(service_with_client) -> None:
    service, _ = service_with_client

    with pytest.raises(ValueError, match="exactly one"):
        await service.search_structural_variants(sv_dataset="gnomad_sv_r4")

    with pytest.raises(ValueError, match="exactly one"):
        await service.search_structural_variants(
            gene_symbol="SMARCA4", region="19-1-2", sv_dataset="gnomad_sv_r4"
        )


@pytest.mark.asyncio
async def test_invalid_sv_dataset_rejected(service_with_client) -> None:
    service, _ = service_with_client

    with pytest.raises(ValueError, match="sv_dataset"):
        await service.search_structural_variants(
            gene_symbol="SMARCA4", sv_dataset="gnomad_r4"
        )


@pytest.mark.asyncio
async def test_malformed_region_rejected(service_with_client) -> None:
    service, _ = service_with_client

    with pytest.raises(ValueError, match="region"):
        await service.search_structural_variants(
            region="not-a-region", sv_dataset="gnomad_sv_r4"
        )
```

- [ ] **Step 2: Run the failing test**

Run: `uv run pytest tests/unit/services/test_structural_variant_service.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'gnomad_link.services.structural_variant_service'`.

- [ ] **Step 3: Add the GraphQL document**

Create `gnomad_link/graphql/queries/common/sv_search.graphql` with two named operations. The loader resolves a document by file stem (`sv_search`); both the gene and region queries live in the same document and the client selects the operation by name via `gql(...)`. Field set matches the VERIFIED schema; the upstream fields take no filter args.

```graphql
query sv_search_by_gene(
    $gene_id: String
    $gene_symbol: String
    $reference_genome: ReferenceGenomeId!
    $sv_dataset: StructuralVariantDatasetId!
) {
    gene(gene_id: $gene_id, gene_symbol: $gene_symbol, reference_genome: $reference_genome) {
        structural_variants(dataset: $sv_dataset) {
            variant_id
            type
            chrom
            pos
            end
            length
            af
            ac
            an
            major_consequence
        }
    }
}

query sv_search_by_region(
    $chrom: String!
    $start: Int!
    $stop: Int!
    $reference_genome: ReferenceGenomeId!
    $sv_dataset: StructuralVariantDatasetId!
) {
    region(chrom: $chrom, start: $start, stop: $stop, reference_genome: $reference_genome) {
        structural_variants(dataset: $sv_dataset) {
            variant_id
            type
            chrom
            pos
            end
            length
            af
            ac
            an
            major_consequence
        }
    }
}
```

- [ ] **Step 4: Add client methods**

In `gnomad_link/api/client.py`, append two methods to `UnifiedGnomadClient`. The `QueryBuilder.process_variables` path has no `sv_search` branch, so it passes variables through unchanged — pass `reference_genome` and `sv_dataset` explicitly. The version arg to `execute_query` is effectively unused here: these are `common/`-only documents resolved by file stem (no per-version variants exist), and the query is build-parameterised via `$reference_genome`, not version-specific. (`QueryBuilder.DATASET_VERSIONS` maps `gnomad_sv_r2_1`→`v2` and `gnomad_sv_r4`→`v4`, but that mapping is irrelevant for a common-only doc selected by stem.) Load by the operation name so `gql()` parses only the requested operation.

```python
    async def search_structural_variants_by_gene(
        self,
        *,
        gene_id: str | None,
        gene_symbol: str | None,
        reference_genome: str,
        sv_dataset: str = "gnomad_sv_r4",
    ) -> list[dict[str, Any]]:
        """Search structural variants overlapping a gene.

        Args:
            gene_id: Ensembl gene ID (mutually exclusive with gene_symbol)
            gene_symbol: HGNC gene symbol
            reference_genome: GRCh37 or GRCh38 (derived from sv_dataset)
            sv_dataset: StructuralVariantDatasetId enum value

        Returns:
            Flat list of structural variant rows (may be empty)
        """
        variables: dict[str, Any] = {
            "gene_id": gene_id,
            "gene_symbol": gene_symbol,
            "reference_genome": reference_genome,
            "sv_dataset": sv_dataset,
        }
        result = await self.execute_query(
            "sv_search_by_gene", variables, "v4"
        )
        gene = result.get("gene") or {}
        return list(gene.get("structural_variants") or [])

    async def search_structural_variants_by_region(
        self,
        *,
        chrom: str,
        start: int,
        stop: int,
        reference_genome: str,
        sv_dataset: str = "gnomad_sv_r4",
    ) -> list[dict[str, Any]]:
        """Search structural variants overlapping a region.

        Args:
            chrom: Chromosome (no chr prefix)
            start: 1-based start position
            stop: 1-based stop position
            reference_genome: GRCh37 or GRCh38 (derived from sv_dataset)
            sv_dataset: StructuralVariantDatasetId enum value

        Returns:
            Flat list of structural variant rows (may be empty)
        """
        variables: dict[str, Any] = {
            "chrom": chrom,
            "start": start,
            "stop": stop,
            "reference_genome": reference_genome,
            "sv_dataset": sv_dataset,
        }
        result = await self.execute_query(
            "sv_search_by_region", variables, "v4"
        )
        region = result.get("region") or {}
        return list(region.get("structural_variants") or [])
```

The loader resolves `sv_search_by_gene` / `sv_search_by_region` by file stem. Because both operations live in one `sv_search.graphql` file (and neither stem matches a file), add per-operation lookup: in `execute_query` the query name is used both to load the file AND to detect the not-found sentinel (`result[query_name] is None`). To keep the loader and not-found logic working without a loader change, name the files by operation. Create the document above as `gnomad_link/graphql/queries/common/sv_search_by_gene.graphql` (the gene query only) and `gnomad_link/graphql/queries/common/sv_search_by_region.graphql` (the region query only), each containing a single operation. The data envelope key is `gene` / `region`, which the methods read directly (NOT keyed by the operation name), so the `result[query_name] is None` sentinel in `execute_query` never trips for `sv_search_by_*` (the key is absent), and DataNotFoundError surfaces only via `TransportQueryError` "not found" classification. Delete the combined `sv_search.graphql` from Step 3 and use the two single-operation files instead.

`gnomad_link/graphql/queries/common/sv_search_by_gene.graphql`:

```graphql
query sv_search_by_gene(
    $gene_id: String
    $gene_symbol: String
    $reference_genome: ReferenceGenomeId!
    $sv_dataset: StructuralVariantDatasetId!
) {
    gene(gene_id: $gene_id, gene_symbol: $gene_symbol, reference_genome: $reference_genome) {
        structural_variants(dataset: $sv_dataset) {
            variant_id
            type
            chrom
            pos
            end
            length
            af
            ac
            an
            major_consequence
        }
    }
}
```

`gnomad_link/graphql/queries/common/sv_search_by_region.graphql`:

```graphql
query sv_search_by_region(
    $chrom: String!
    $start: Int!
    $stop: Int!
    $reference_genome: ReferenceGenomeId!
    $sv_dataset: StructuralVariantDatasetId!
) {
    region(chrom: $chrom, start: $start, stop: $stop, reference_genome: $reference_genome) {
        structural_variants(dataset: $sv_dataset) {
            variant_id
            type
            chrom
            pos
            end
            length
            af
            ac
            an
            major_consequence
        }
    }
}
```

- [ ] **Step 5: Add the StructuralVariantService**

Create `gnomad_link/services/structural_variant_service.py` (heavy orchestration lives here, NOT in `frequency_service.py`):

```python
"""Service for searching gnomAD structural variants by gene or region.

Heavy orchestration (entry-arg dispatch, sv_dataset->build mapping, region
parsing) lives here so FrequencyService keeps only a thin delegating wrapper
and does not grow past its line budget. Client-side filtering and capping
live in gnomad_link/mcp/sv_shaping.py, not here.
"""

from __future__ import annotations

import re
from typing import Any

from gnomad_link.api.client import UnifiedGnomadClient

# StructuralVariantDatasetId -> reference build. gnomad_sv_r4 is GRCh38;
# gnomad_sv_r2_1 is GRCh37. This is a DISTINCT enum from the SNV DatasetId.
_SV_DATASET_BUILD: dict[str, str] = {
    "gnomad_sv_r4": "GRCh38",
    "gnomad_sv_r2_1": "GRCh37",
}

_REGION_RE = re.compile(r"^(?:chr)?([1-9]|1\d|2[0-2]|X|Y)-(\d+)-(\d+)$")


class StructuralVariantService:
    """Search structural variants overlapping a gene or region."""

    def __init__(self, client: UnifiedGnomadClient | None = None) -> None:
        self.client = client or UnifiedGnomadClient()

    async def search_structural_variants(
        self,
        *,
        gene_symbol: str | None = None,
        gene_id: str | None = None,
        region: str | None = None,
        sv_dataset: str = "gnomad_sv_r4",
    ) -> list[dict[str, Any]]:
        """Return the FULL list of SV rows for the entry argument.

        Exactly one of gene_symbol / gene_id / region must be provided.
        Filtering and capping are the caller's responsibility (sv_shaping).
        """
        provided = [v for v in (gene_symbol, gene_id, region) if v]
        if len(provided) != 1:
            raise ValueError(
                "Provide exactly one of gene_symbol, gene_id, or region."
            )
        if sv_dataset not in _SV_DATASET_BUILD:
            raise ValueError(
                "Invalid sv_dataset; expected gnomad_sv_r4 or gnomad_sv_r2_1."
            )
        reference_genome = _SV_DATASET_BUILD[sv_dataset]

        if region:
            match = _REGION_RE.match(region)
            if not match:
                raise ValueError(
                    "Invalid region; expected CHROM-START-STOP (e.g. 19-11089000-11200000)."
                )
            chrom, start_s, stop_s = match.groups()
            start, stop = int(start_s), int(stop_s)
            if stop <= start:
                raise ValueError("Region stop must be greater than start.")
            return await self.client.search_structural_variants_by_region(
                chrom=chrom,
                start=start,
                stop=stop,
                reference_genome=reference_genome,
                sv_dataset=sv_dataset,
            )

        return await self.client.search_structural_variants_by_gene(
            gene_id=gene_id,
            gene_symbol=gene_symbol,
            reference_genome=reference_genome,
            sv_dataset=sv_dataset,
        )
```

- [ ] **Step 6: Add the thin FrequencyService delegating method**

In `gnomad_link/services/frequency_service.py`, in the "Thin pass-through wrappers" block at the end of the class, append (keeps `frequency_service.py` growth to a few lines; orchestration is in `StructuralVariantService`):

```python
    async def search_structural_variants(
        self,
        *,
        gene_symbol: str | None = None,
        gene_id: str | None = None,
        region: str | None = None,
        sv_dataset: str = "gnomad_sv_r4",
    ) -> list[dict[str, Any]]:
        """Delegate SV search to StructuralVariantService over the shared client."""
        from gnomad_link.services.structural_variant_service import (
            StructuralVariantService,
        )

        return await StructuralVariantService(client=self.client).search_structural_variants(
            gene_symbol=gene_symbol,
            gene_id=gene_id,
            region=region,
            sv_dataset=sv_dataset,
        )
```

- [ ] **Step 7: Run the test**

Run: `uv run pytest tests/unit/services/test_structural_variant_service.py -q`
Expected: PASS (7 passed).

- [ ] **Step 8: Run full local CI**

Run: `make ci-local`
Expected: PASS.

- [ ] **Step 9: Commit**

```
git add gnomad_link/graphql/queries/common/sv_search_by_gene.graphql gnomad_link/graphql/queries/common/sv_search_by_region.graphql gnomad_link/services/structural_variant_service.py gnomad_link/api/client.py gnomad_link/services/frequency_service.py tests/unit/services/test_structural_variant_service.py
git commit -m "feat(mcp): add structural-variant search GraphQL, client, and service for gene/region SV lookup"
```

---

### Task C5.2: sv_shaping.py — client-side type/length filter, cap, truncated block, compact rows

**Files:**
- Create: `gnomad_link/mcp/sv_shaping.py`
- Create: `tests/unit/mcp/test_sv_shaping.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/mcp/test_sv_shaping.py`:

```python
"""Unit tests for SV search shaping (filter + cap + truncated + compact rows).

Mirrors the shape_gene_variants truncation contract: total_seen counts the
FULL upstream list (before the cap), the truncated block reports dropped
counts and a to_restore/to_disable hint, and compact rows are projected to a
fixed keep-set.
"""

from __future__ import annotations

from gnomad_link.mcp.sv_shaping import shape_sv_search

_ROWS = [
    {
        "variant_id": "DEL_19_1",
        "type": "DEL",
        "chrom": "19",
        "pos": 11_089_000,
        "end": 11_133_820,
        "length": 44_820,
        "af": 0.0001,
        "ac": 3,
        "an": 30000,
        "major_consequence": "lof",
        "consequences": [{"consequence": "lof", "genes": ["SMARCA4"]}],
    },
    {
        "variant_id": "DUP_19_2",
        "type": "DUP",
        "chrom": "19",
        "pos": 11_100_000,
        "end": 11_200_000,
        "length": 100_000,
        "af": 0.002,
        "ac": 60,
        "an": 30000,
        "major_consequence": "copy_gain",
    },
    {
        "variant_id": "DEL_19_3",
        "type": "DEL",
        "chrom": "19",
        "pos": 11_300_000,
        "end": 11_300_500,
        "length": 500,
        "af": 0.01,
        "ac": 300,
        "an": 30000,
        "major_consequence": "lof",
    },
]


def test_no_filters_returns_all_with_compact_rows() -> None:
    out = shape_sv_search(_ROWS, sv_type=None, min_length=None, max_length=None, limit=100)

    assert out["returned"] == 3
    assert out["total_seen"] == 3
    assert "truncated" not in out
    # Compact rows keep only the advertised key-set.
    first = out["structural_variants"][0]
    assert set(first) == {
        "variant_id",
        "type",
        "chrom",
        "pos",
        "end",
        "length",
        "af",
        "ac",
        "an",
        "major_consequence",
    }
    assert "consequences" not in first


def test_filter_by_sv_type() -> None:
    out = shape_sv_search(_ROWS, sv_type="DEL", min_length=None, max_length=None, limit=100)

    assert [r["variant_id"] for r in out["structural_variants"]] == ["DEL_19_1", "DEL_19_3"]
    assert out["returned"] == 2
    assert out["total_seen"] == 3
    assert out["truncated"]["kind"] == "structural_variants"
    assert out["truncated"]["dropped"] == 1
    assert out["truncated"]["filter"] == {
        "sv_type": "DEL",
        "min_length": None,
        "max_length": None,
    }


def test_filter_by_length_window() -> None:
    out = shape_sv_search(
        _ROWS, sv_type=None, min_length=1000, max_length=50_000, limit=100
    )

    # Only DEL_19_1 (44820) is in [1000, 50000].
    assert [r["variant_id"] for r in out["structural_variants"]] == ["DEL_19_1"]
    assert out["returned"] == 1
    assert out["total_seen"] == 3
    assert out["truncated"]["dropped"] == 2


def test_cap_to_limit_emits_truncated() -> None:
    out = shape_sv_search(_ROWS, sv_type=None, min_length=None, max_length=None, limit=2)

    assert out["returned"] == 2
    assert out["total_seen"] == 3
    assert out["truncated"]["kind"] == "structural_variants"
    assert out["truncated"]["dropped"] == 1
    assert out["truncated"]["to_restore"] == "limit=3"
    assert "to_disable" in out["truncated"]


def test_empty_input_returns_zero_no_truncated() -> None:
    out = shape_sv_search([], sv_type=None, min_length=None, max_length=None, limit=100)

    assert out["returned"] == 0
    assert out["total_seen"] == 0
    assert out["structural_variants"] == []
    assert "truncated" not in out
```

- [ ] **Step 2: Run the failing test**

Run: `uv run pytest tests/unit/mcp/test_sv_shaping.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'gnomad_link.mcp.sv_shaping'`.

- [ ] **Step 3: Implement sv_shaping.py**

Create `gnomad_link/mcp/sv_shaping.py` (NEVER add this to `shaping.py`). Mirrors `shape_gene_variants`'s pattern (`total_seen` from the FULL list, `dropped` counts, `to_restore`/`to_disable`) and `_project_row`'s keep-set projection:

```python
"""Client-side filtering, capping, and compact projection for SV search.

Upstream gene/region structural_variants fields take no filter arguments, so
all filtering (sv_type, min_length, max_length) and the limit cap happen here.
Pattern mirrors shaping.shape_gene_variants: total_seen reflects the FULL
list before any cap, and a self-describing truncated block reports the most
useful restore hint.
"""

from __future__ import annotations

from typing import Any

# Compact projection key-set. Drops heavy fields (consequences, populations,
# cpx_intervals, ...) the list view does not need; callers fetch the full
# payload per id via get_structural_variant.
_SV_ROW_KEEP = {
    "variant_id",
    "type",
    "chrom",
    "pos",
    "end",
    "length",
    "af",
    "ac",
    "an",
    "major_consequence",
}


def _project_sv_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k in _SV_ROW_KEEP}


def shape_sv_search(
    raw: list[dict[str, Any]],
    *,
    sv_type: str | None,
    min_length: int | None,
    max_length: int | None,
    limit: int,
) -> dict[str, Any]:
    """Filter, cap, and compact-project a structural-variant list.

    Filtering is case-insensitive on sv_type. min_length/max_length apply to
    each row's `length`; rows without a length are dropped when a length
    filter is active. Emits a `truncated` block when any filter drops rows or
    when the limit cap fires; `total_seen` always reflects the FULL input.
    """
    if limit <= 0 or limit > 500:
        raise ValueError("limit must be in [1, 500]")

    total_seen = len(raw)
    dropped = {"by_sv_type": 0, "by_min_length": 0, "by_max_length": 0}
    wanted_type = sv_type.upper() if sv_type else None

    filtered: list[dict[str, Any]] = []
    for row in raw:
        if wanted_type is not None and str(row.get("type") or "").upper() != wanted_type:
            dropped["by_sv_type"] += 1
            continue
        length = row.get("length")
        if min_length is not None and (length is None or length < min_length):
            dropped["by_min_length"] += 1
            continue
        if max_length is not None and (length is None or length > max_length):
            dropped["by_max_length"] += 1
            continue
        filtered.append(row)

    capped = filtered[:limit]
    cap_dropped = len(filtered) - len(capped)
    rows = [_project_sv_row(r) for r in capped]

    payload: dict[str, Any] = {
        "structural_variants": rows,
        "returned": len(rows),
        "total_seen": total_seen,
    }

    any_filter_dropped = sum(dropped.values()) > 0
    if any_filter_dropped or cap_dropped > 0:
        # Restore hint targets the cap first (a single int bump), then the
        # most-dropped filter category.
        restore_mapping = {
            "by_sv_type": "sv_type=None (remove type filter)",
            "by_min_length": "min_length=None (remove length floor)",
            "by_max_length": "max_length=None (remove length ceiling)",
        }
        if cap_dropped > 0:
            to_restore: str | None = f"limit={min(len(filtered), 500)}"
        else:
            best_key: str | None = None
            best_count = 0
            for key, count in dropped.items():
                if count > best_count:
                    best_count = count
                    best_key = key
            to_restore = restore_mapping.get(best_key or "")
        truncated: dict[str, Any] = {
            "kind": "structural_variants",
            "dropped": sum(dropped.values()) + cap_dropped,
            "filter": {
                "sv_type": sv_type,
                "min_length": min_length,
                "max_length": max_length,
            },
            "to_disable": (
                "raise limit (max 500) or relax sv_type/min_length/max_length filters"
            ),
        }
        if to_restore:
            truncated["to_restore"] = to_restore
        payload["truncated"] = truncated

    return payload
```

- [ ] **Step 4: Run the test**

Run: `uv run pytest tests/unit/mcp/test_sv_shaping.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Run full local CI**

Run: `make ci-local`
Expected: PASS.

- [ ] **Step 6: Commit**

```
git add gnomad_link/mcp/sv_shaping.py tests/unit/mcp/test_sv_shaping.py
git commit -m "feat(mcp): add sv_shaping for client-side SV filter, cap, and compact rows"
```

---

### Task C5.3: search_structural_variants tool + capabilities/parity sync

**Files:**
- Create: `gnomad_link/mcp/tools/sv_search.py`
- Modify: `gnomad_link/mcp/tools/__init__.py`
- Modify: `gnomad_link/mcp/resources.py`
- Create: `tests/unit/mcp/test_sv_search_tool.py`
- Modify: `tests/unit/mcp/test_mcp_facade_surface.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/mcp/test_sv_search_tool.py`:

```python
"""Tool-surface tests for search_structural_variants.

Offline: the service factory returns a spy whose search_structural_variants
returns a fixed SV list. Exercises entry-arg dispatch, the DISTINCT sv_dataset
Literal, client-side filters, the empty->success contract, and the
next_commands cross-link to get_structural_variant.
"""

from __future__ import annotations

import pytest

_ROWS = [
    {
        "variant_id": "DEL_19_1",
        "type": "DEL",
        "chrom": "19",
        "pos": 11_089_000,
        "end": 11_133_820,
        "length": 44_820,
        "af": 0.0001,
        "ac": 3,
        "an": 30000,
        "major_consequence": "lof",
    },
    {
        "variant_id": "DUP_19_2",
        "type": "DUP",
        "chrom": "19",
        "pos": 11_100_000,
        "end": 11_200_000,
        "length": 100_000,
        "af": 0.002,
        "ac": 60,
        "an": 30000,
        "major_consequence": "copy_gain",
    },
]


class _SpySvService:
    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        self.rows = _ROWS if rows is None else rows
        self.last_kwargs: dict[str, object] | None = None

    async def search_structural_variants(
        self,
        *,
        gene_symbol: str | None = None,
        gene_id: str | None = None,
        region: str | None = None,
        sv_dataset: str = "gnomad_sv_r4",
    ) -> list[dict[str, object]]:
        self.last_kwargs = {
            "gene_symbol": gene_symbol,
            "gene_id": gene_id,
            "region": region,
            "sv_dataset": sv_dataset,
        }
        return self.rows


@pytest.mark.asyncio
async def test_search_by_gene_symbol_returns_rows() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _SpySvService()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "search_structural_variants",
        {"gene_symbol": "SMARCA4", "sv_dataset": "gnomad_sv_r4"},
    )
    payload = result.structured_content or {}

    assert payload.get("error_code") != "validation_failed", payload
    assert payload["query"] == {"gene_symbol": "SMARCA4", "sv_dataset": "gnomad_sv_r4"}
    assert payload["returned"] == 2
    assert payload["total_seen"] == 2
    assert spy.last_kwargs["gene_symbol"] == "SMARCA4"


@pytest.mark.asyncio
async def test_distinct_sv_dataset_default_is_r4() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _SpySvService()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "search_structural_variants", {"gene_symbol": "SMARCA4"}
    )
    payload = result.structured_content or {}

    assert payload.get("error_code") != "validation_failed", payload
    assert spy.last_kwargs["sv_dataset"] == "gnomad_sv_r4"


@pytest.mark.asyncio
async def test_invalid_sv_dataset_rejected_by_schema() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _SpySvService()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    # gnomad_r4 is the SNV DatasetId, NOT a StructuralVariantDatasetId.
    result = await mcp.call_tool(
        "search_structural_variants",
        {"gene_symbol": "SMARCA4", "sv_dataset": "gnomad_r4"},
    )
    payload = result.structured_content or {}

    assert payload.get("success") is False
    assert payload.get("error_code") == "validation_failed"
    assert spy.last_kwargs is None


@pytest.mark.asyncio
async def test_requires_exactly_one_entry_arg() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _SpySvService()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    none_result = await mcp.call_tool("search_structural_variants", {})
    none_payload = none_result.structured_content or {}
    assert none_payload.get("error_code") == "validation_failed"

    both_result = await mcp.call_tool(
        "search_structural_variants",
        {"gene_symbol": "SMARCA4", "region": "19-11089000-11200000"},
    )
    both_payload = both_result.structured_content or {}
    assert both_payload.get("error_code") == "validation_failed"


@pytest.mark.asyncio
async def test_sv_type_filter_applied() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _SpySvService()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "search_structural_variants",
        {"gene_symbol": "SMARCA4", "sv_type": "DEL"},
    )
    payload = result.structured_content or {}

    assert [r["variant_id"] for r in payload["structural_variants"]] == ["DEL_19_1"]
    assert payload["truncated"]["kind"] == "structural_variants"
    assert payload["truncated"]["dropped"] == 1


@pytest.mark.asyncio
async def test_empty_result_is_success_not_error() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _SpySvService(rows=[])
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "search_structural_variants", {"gene_symbol": "NONEXISTENT"}
    )
    payload = result.structured_content or {}

    assert payload.get("success") is not False
    assert payload["returned"] == 0
    assert payload["total_seen"] == 0
    assert payload["structural_variants"] == []


@pytest.mark.asyncio
async def test_next_commands_link_to_get_structural_variant() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _SpySvService()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "search_structural_variants", {"gene_symbol": "SMARCA4"}
    )
    payload = result.structured_content or {}
    next_commands = payload["_meta"]["next_commands"]

    assert len(next_commands) <= 3
    assert all(cmd["tool"] == "get_structural_variant" for cmd in next_commands)
    ids = [cmd["arguments"]["variant_id"] for cmd in next_commands]
    assert ids == ["DEL_19_1", "DUP_19_2"]
    assert all(
        cmd["arguments"]["dataset"] == "gnomad_sv_r4" for cmd in next_commands
    )


@pytest.mark.asyncio
async def test_region_dispatch_forwards_region() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    spy = _SpySvService()
    mcp = create_gnomad_mcp(service_factory=lambda: spy)

    result = await mcp.call_tool(
        "search_structural_variants",
        {"region": "19-11089000-11200000", "sv_dataset": "gnomad_sv_r2_1"},
    )
    payload = result.structured_content or {}

    assert payload.get("error_code") != "validation_failed", payload
    assert spy.last_kwargs["region"] == "19-11089000-11200000"
    assert spy.last_kwargs["sv_dataset"] == "gnomad_sv_r2_1"
    assert payload["query"]["region"] == "19-11089000-11200000"


@pytest.mark.asyncio
async def test_tool_is_registered_with_variant_tag_and_open_world() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp

    mcp = create_gnomad_mcp(service_factory=lambda: _SpySvService())
    tools_by_name = {tool.name: tool for tool in await mcp.list_tools()}

    assert "search_structural_variants" in tools_by_name
    tool = tools_by_name["search_structural_variants"]
    assert tool.tags == {"variant", "search"}
    assert tool.annotations is not None
    assert tool.annotations.openWorldHint is True
```

Also extend `tests/unit/mcp/test_mcp_facade_surface.py`: add `"search_structural_variants"` to `EXPECTED_TOOLS`. (The `test_capabilities_tools_match_facade_tools` parity gate and `test_capabilities_resource_lists_token_cost_hints` then enforce the resources.py sync in Step 4.)

- [ ] **Step 2: Run the failing tests**

Run: `uv run pytest tests/unit/mcp/test_sv_search_tool.py tests/unit/mcp/test_mcp_facade_surface.py -q`
Expected: FAIL — `search_structural_variants` is not registered (tool-call errors / `test_capabilities_tools_match_facade_tools` mismatch / `EXPECTED_TOOLS` not satisfied).

- [ ] **Step 3: Implement the tool module**

Create `gnomad_link/mcp/tools/sv_search.py`. The `sv_dataset` Literal is the DISTINCT `StructuralVariantDatasetId` enum values (NOT `gnomad_r2_1/r3/r4`). The `variant_id` docstring states SV ids are opaque so no CHROM-POS-REF-ALT regex is applied:

```python
"""Structural-variant search tool: search_structural_variants."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from gnomad_link.mcp.annotations import READ_ONLY_OPEN_WORLD
from gnomad_link.mcp.errors import McpErrorContext, run_mcp_tool
from gnomad_link.mcp.schema_relax import relax_output_schema
from gnomad_link.mcp.sv_shaping import shape_sv_search
from gnomad_link.services import FrequencyService

# Cap how many returned ids become next_commands (no self-reference; <=3).
_NEXT_COMMAND_CAP = 3

_SV_SEARCH_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "object"},
        "returned": {"type": "integer"},
        "total_seen": {"type": "integer"},
        "structural_variants": {"type": "array", "items": {"type": "object"}},
        "truncated": {"type": ["object", "null"]},
    },
    "required": ["query", "returned", "total_seen", "structural_variants"],
    "additionalProperties": True,
}


def register_sv_search_tools(
    mcp: FastMCP, *, service_factory: Callable[[], FrequencyService]
) -> None:
    @mcp.tool(
        name="search_structural_variants",
        title="Search Structural Variants in a Gene or Region",
        annotations=READ_ONLY_OPEN_WORLD,
        output_schema=relax_output_schema(_SV_SEARCH_OUTPUT_SCHEMA),
        tags={"variant", "search"},
    )
    async def search_structural_variants(
        gene_symbol: Annotated[
            str | None,
            Field(
                description="HGNC gene symbol. Provide exactly one of gene_symbol, gene_id, or region.",
                examples=["SMARCA4"],
            ),
        ] = None,
        gene_id: Annotated[
            str | None,
            Field(
                description="Ensembl gene ID (preferred over symbol).",
                examples=["ENSG00000127616"],
            ),
        ] = None,
        region: Annotated[
            str | None,
            Field(
                description="Region in CHROM-START-STOP format (e.g. 19-11089000-11200000).",
                examples=["19-11089000-11200000"],
            ),
        ] = None,
        sv_dataset: Annotated[
            Literal["gnomad_sv_r4", "gnomad_sv_r2_1"],
            Field(
                description=(
                    "Structural-variant dataset (DISTINCT from SNV datasets). "
                    "gnomad_sv_r4 (GRCh38, default), gnomad_sv_r2_1 (GRCh37)."
                ),
                examples=["gnomad_sv_r4"],
            ),
        ] = "gnomad_sv_r4",
        sv_type: Annotated[
            str | None,
            Field(
                description="Filter by SV class (e.g. DEL, DUP, INS, INV, BND, CPX). Case-insensitive.",
                examples=["DEL"],
            ),
        ] = None,
        min_length: Annotated[
            int | None,
            Field(ge=0, description="Drop SVs shorter than this length (bp)."),
        ] = None,
        max_length: Annotated[
            int | None,
            Field(ge=0, description="Drop SVs longer than this length (bp)."),
        ] = None,
        limit: Annotated[
            int,
            Field(ge=1, le=500, description="Max SV rows returned (hard cap 500)."),
        ] = 100,
        response_mode: Annotated[
            Literal["compact", "full"],
            Field(description="compact projects each row to a fixed key-set; full is reserved."),
        ] = "compact",
    ) -> dict[str, Any]:
        """Use this when a caller wants the list of structural variants overlapping a gene or region. Provide exactly one of gene_symbol, gene_id, or region. SV variant_id values are OPAQUE (e.g. DEL_19_1), NOT CHROM-POS-REF-ALT, so no SNV id grammar is applied; fetch a single SV by id with get_structural_variant. sv_dataset is the DISTINCT structural-variant dataset enum (gnomad_sv_r4=GRCh38 default, gnomad_sv_r2_1=GRCh37), not the SNV dataset. Type/length filters are applied client-side. An empty match is a success with returned=0, not an error. Returns ~3-30kB (limit-dependent)."""

        async def call() -> dict[str, Any]:
            provided = [v for v in (gene_symbol, gene_id, region) if v]
            if len(provided) != 1:
                raise ValueError(
                    "Provide exactly one of gene_symbol, gene_id, or region."
                )
            service = service_factory()
            raw = await service.search_structural_variants(
                gene_symbol=gene_symbol,
                gene_id=gene_id,
                region=region,
                sv_dataset=sv_dataset,
            )
            shaped = shape_sv_search(
                raw,
                sv_type=sv_type,
                min_length=min_length,
                max_length=max_length,
                limit=limit,
            )
            query_echo: dict[str, Any] = {"sv_dataset": sv_dataset}
            if gene_id:
                query_echo = {"gene_id": gene_id, "sv_dataset": sv_dataset}
            elif gene_symbol:
                query_echo = {"gene_symbol": gene_symbol, "sv_dataset": sv_dataset}
            elif region:
                query_echo = {"region": region, "sv_dataset": sv_dataset}
            shaped["query"] = query_echo
            # Cross-link each returned opaque id to the single-SV detail tool.
            existing_meta: dict[str, Any] = shaped.get("_meta") or {}
            existing_next: list[Any] = existing_meta.get("next_commands", [])
            next_commands = [
                {
                    "tool": "get_structural_variant",
                    "arguments": {"variant_id": row["variant_id"], "dataset": sv_dataset},
                }
                for row in shaped["structural_variants"][:_NEXT_COMMAND_CAP]
                if row.get("variant_id")
            ]
            shaped["_meta"] = {
                **existing_meta,
                "next_commands": [*existing_next, *next_commands],
            }
            return shaped

        return await run_mcp_tool(
            "search_structural_variants",
            call,
            context=McpErrorContext(
                tool_name="search_structural_variants",
                gene_id=gene_id,
                gene_symbol=gene_symbol,
                region=region,
                dataset=sv_dataset,
            ),
        )
```

Wire the new module in `gnomad_link/mcp/tools/__init__.py` with ONE import and ONE call line:

```python
from gnomad_link.mcp.tools.sv_search import register_sv_search_tools
```

and inside `register_gnomad_tools`, after `register_specialty_tools(...)`:

```python
    register_sv_search_tools(mcp, service_factory=service_factory)
```

- [ ] **Step 4: Sync resources.py (same task as registration)**

In `gnomad_link/mcp/resources.py` `get_capabilities_resource()`:

Append `"search_structural_variants"` to the `tools` list (place it after `"get_structural_variant"`):

```python
            "get_structural_variant",
            "search_structural_variants",
```

Add a `token_cost_hints` entry (<=80 chars), after the `get_structural_variant` line:

```python
            "get_structural_variant": "~1-3kB",
            "search_structural_variants": "~3-30kB (limit-dependent)",
```

Add it to `tool_categories` under both `variant` and `search`:

```python
            "variant": [
                "get_variant_frequencies",
                "get_variant_details",
                "get_mitochondrial_variant",
                "get_structural_variant",
                "search_structural_variants",
            ],
```
```python
            "search": ["search_genes", "resolve_variant_id", "search_variants", "search_structural_variants"],
```

- [ ] **Step 5: Run the focused tests**

Run: `uv run pytest tests/unit/mcp/test_sv_search_tool.py tests/unit/mcp/test_mcp_facade_surface.py -q`
Expected: PASS (all green, including `test_capabilities_tools_match_facade_tools` and `test_capabilities_resource_lists_token_cost_hints`).

- [ ] **Step 6: Run full local CI**

Run: `make ci-local`
Expected: PASS (format, lint, lint-loc, typecheck, tests; no module exceeds 600 LOC; no `.loc-allowlist` change).

- [ ] **Step 7: Commit**

```
git add gnomad_link/mcp/tools/sv_search.py gnomad_link/mcp/tools/__init__.py gnomad_link/mcp/resources.py tests/unit/mcp/test_sv_search_tool.py tests/unit/mcp/test_mcp_facade_surface.py
git commit -m "feat(mcp): add search_structural_variants tool with gene/region dispatch and SV dataset enum"
```

---

## Done Criteria

- [ ] All 21 tools register; `make mcp-serve` (stdio) and the HTTP host start without error.
- [ ] `make ci-local` passes (format, lint, `lint-loc`, typecheck, unit tests) on the final commit.
- [ ] Five new tools present in `get_server_capabilities` / `gnomad://capabilities` with `token_cost_hints` (≤80 chars) and correct `tool_categories`; `test_capabilities_tools_match_facade_tools` green.
- [ ] `EXPECTED_TOOLS` in `tests/unit/mcp/test_mcp_facade_surface.py` contains all five; the `EXPECTED_DATA_TOOLS` sweeps (annotations, `relax_output_schema`, `Use this when …` docstrings) pass for each.
- [ ] Every new module is < 600 LOC; `shaping.py` and `frequency_service.py` unchanged in size beyond thin delegates; `.loc-allowlist` unchanged.
- [ ] No new Ruff/mypy ignores added.
- [ ] Each new tool emits the research-use safety meta (`unsafe_for_clinical_use`, `gnomad_release`) and a sensible `_meta.next_commands` chain.
- [ ] C3 `carrier_math.py` golden-value tests pass (CFTR-like q=0.023 → 2pq=0.044942, q²=0.000529; q=0.011 → 2pq=0.021758); AR/AD/XL + Wilson CI covered.
- [ ] C2 returns per-dataset partial-success (`present:false` on 404), `upstream_unavailable` only when all datasets fail, and auto-lifts GRCh38→GRCh37 for `gnomad_r2_1`.
- [ ] C4 sources pathogenic ClinVar from `Gene.clinvar_variants` (no 100kb cap) and backfills expression from GRCh37 best-effort; the `integration`-marked live test confirms GRCh37-vs-GRCh38 expression population.
- [ ] C1 supports gene + region + variant scopes, caps coverage bins with a `truncated` block, reuses `cap_region_span(100kb)`, and raises `build_mismatch` on region/dataset build clashes.
- [ ] C5 uses the distinct `StructuralVariantDatasetId` enum, filters `sv_type`/length client-side with a `truncated` block, treats an empty match as success (`returned:0`), and applies no SNV id grammar to opaque SV ids.
- [ ] All commits are atomic and follow the `feat(mcp):` / `refactor(mcp):` / `chore(mcp):` convention.

## Out of Scope

- Transcript-level and mitochondrial coverage (C1 v1 is gene + region + variant only).
- The r4-only `joint.freq_comparison_stats` contingency/CMH tests (C2).
- Gene-level (multi-variant summed) carrier frequency, and X-linked hemizygote-count math beyond XX/XY allele-number derivation (C3 is per-variant).
- Cross-MCP expression calls (e.g. gtex-link) — only gnomAD's own pext/GTEx is surfaced (C4).
- Copy-number variants, short tandem repeats, and other gene-level tracks not listed above.
- Any new REST surface — the FastAPI host stays `/health` only; all behavior is MCP.
- Clinical decision support of any kind — research use only.
