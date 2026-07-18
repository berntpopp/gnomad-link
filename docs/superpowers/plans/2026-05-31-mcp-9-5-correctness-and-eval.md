# gnomAD Link MCP 9.5/10 — Implementation Plan

> Historical record

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the gnomAD Link MCP from ~8.1-8.9 to a measured >=9.4/10 by fixing the one HIGH correctness bug, building the eval harness that gates the rest, and closing residual contract/token gaps — all additive, non-breaking.

**Architecture:** Five sequential phases, each a commit boundary. Phase 1 (correctness) ships first. Phase 2 builds a deterministic eval harness wired into `ci-local` that scores Phases 3-5. Phases 3-5 are measured against that baseline.

**Tech Stack:** Python 3.12, FastMCP facade, Pydantic models, `respx` (HTTP mock, already a dev dep), pytest, Ruff, mypy, `uv`, Make targets.

Spec: `docs/superpowers/specs/2026-05-31-mcp-9-5-correctness-and-eval-design.md`

**Invariants (every task):** additive only (no tool-name/response-schema break); <=600 LOC/module (`shaping.py` 563, `errors.py` 515 are near cap — new logic in new modules); no new runtime dependencies; no live gnomAD calls in default CI (live tests `integration`-marked); research-use scope only. Run `make test-fast` after each task; `make ci-local` green before each phase handoff. Do NOT push without explicit go-ahead.

---

## File Structure

New files:
- `gnomad_link/mcp/minimal_shaping.py` — per-tool `response_mode='minimal'` projections (Phase 4a)
- `gnomad_link/mcp/next_commands.py` — typed `_meta.next_commands` builders (Phase 3)
- `tests/eval/` — deterministic eval harness package (Phase 2a)
  - `tests/eval/scenarios.py`, `tests/eval/scoring.py`, `tests/eval/fixtures.py`, `tests/eval/test_eval_baseline.py`
- `docs/superpowers/eval-baseline-2026-05-31.md` — committed baseline scorecard (Phase 2a)

Modified files (by phase):
- P1: `gnomad_link/mcp/tools/coordinates.py`, `gnomad_link/mcp/tools/comparison.py`, `tests/unit/mcp/test_compare_variant.py`, `tests/integration/` (new live test)
- P3: `gnomad_link/mcp/tools/search.py`, `gnomad_link/mcp/errors.py`, `gnomad_link/mcp/tools/variants.py`, `gnomad_link/mcp/tools/specialty.py`, `gnomad_link/mcp/tools/genes.py`, `gnomad_link/mcp/resources.py`
- P4: `gnomad_link/mcp/tools/{variants,genes,gene_summary,carrier,gene_carrier,comparison}.py`, `gnomad_link/mcp/sv_shaping.py`, `gnomad_link/mcp/heteroplasmy.py`
- P5: `gnomad_link/mcp/tools/metadata.py`, `gnomad_link/mcp/resources.py`, `README.md`, `docs/` MCP connection guide
- Makefile: `eval-ci`, `eval-live` targets; `ci-local` gains `eval-ci`

---

## Phase 1 — Fix the HIGH correctness bug (ship first)

The bug: `compare_variant_across_datasets` queries the GRCh37 `gnomad_r2_1` leg with the wrong (GRCh38) coordinate, producing a false `present:false`. Root cause: `comparison.py:71` hardcodes `item["liftover"].variant_id` (always GRCh38) instead of resolving by build. The standalone `liftover_variant` (`coordinates.py:75-79`) already does it correctly. Confirmed real API ordering (`liftover_models.py:52-59`): `source`=GRCh37, `liftover`=GRCh38. The existing test fixture inverts these, masking the bug.

### Task 1: Extract a shared build-resolver helper

**Files:**
- Modify: `gnomad_link/mcp/tools/coordinates.py` (add module-level function; rewire `call()` at `:75-79`)

- [ ] **Step 1: Add the helper at module top of `coordinates.py`** (after imports, before `register_*`):

```python
def select_build_variant_id(record: dict[str, Any], target_build: str) -> str | None:
    """Return the liftover entry's variant id whose reference_genome == target_build.

    gnomAD liftover records carry BOTH a GRCh37 ``source`` and a GRCh38
    ``liftover`` entry (see LiftoverResult); pick the one matching the requested
    build regardless of query direction. Returns None when neither entry matches.
    """
    for key in ("source", "liftover"):
        entry = record.get(key) or {}
        if entry.get("reference_genome") == target_build:
            return entry.get("variant_id") or None
    return None
```

- [ ] **Step 2: Rewire the standalone path** — replace the inline loop at `coordinates.py:75-79`:

```python
            for record in results:
                record["target_variant_id"] = select_build_variant_id(record, target)
```

- [ ] **Step 3: Run existing liftover tests to confirm no behavior change**

Run: `uv run pytest tests/unit/mcp -k liftover -v`
Expected: PASS (standalone behavior is identical).

- [ ] **Step 4: Commit**

```bash
git add gnomad_link/mcp/tools/coordinates.py
git commit -m "refactor(mcp): extract select_build_variant_id liftover resolver"
```

### Task 2: Fix the masking test fixture (red), then fix `compare` (green)

**Files:**
- Modify: `tests/unit/mcp/test_compare_variant.py:219-225` (correct fixture to real API ordering)
- Modify: `gnomad_link/mcp/tools/comparison.py:69-76` (`_resolve_r2_1_id`)

- [ ] **Step 1: Correct the inverted fixture** in `test_auto_liftover_converts_grch38_id_for_r2_1` (`:219-225`) so the field labels match the real API (`source`=GRCh37, `liftover`=GRCh38). Swap the two ids/builds:

```python
        liftover_result=[
            {
                "source": {"variant_id": "17-7577121-G-A", "reference_genome": "GRCh37"},
                "liftover": {"variant_id": "17-7673803-G-A", "reference_genome": "GRCh38"},
                "datasets": ["gnomad_r2_1", "gnomad_r4"],
            }
        ],
```

The test's existing assertions stay (`r2["lifted_variant_id"] == "17-7577121-G-A"`, the GRCh37 id; r2_1 freq stub already keyed on `17-7577121-G-A`).

- [ ] **Step 2: Run the test to confirm it now FAILS** (the bug is exposed by the corrected fixture)

Run: `uv run pytest tests/unit/mcp/test_compare_variant.py::test_auto_liftover_converts_grch38_id_for_r2_1 -v`
Expected: FAIL — buggy code reads `liftover` (now GRCh38 `17-7673803-G-A`), queries r2_1 with it, the r2_1 freq stub only has `17-7577121-G-A`, so the leg is `present:false`.

- [ ] **Step 3: Fix `_resolve_r2_1_id`** in `comparison.py` — replace the hardcoded read at `:69-76` with the shared helper:

```python
    results = await service.liftover_variant(variant_id, "GRCh38")
    for item in results:
        lifted = select_build_variant_id(item, "GRCh37")
        if lifted:
            return lifted, (
                f"gnomad_r2_1 (GRCh37) used lifted id {lifted} from GRCh38 {variant_id}."
            )
    return None, (f"gnomad_r2_1 (GRCh37) skipped: no liftover mapping found for {variant_id}.")
```

Add the import at the top of `comparison.py`:

```python
from gnomad_link.mcp.tools.coordinates import select_build_variant_id
```

(If this introduces an import cycle, move `select_build_variant_id` to a new leaf module `gnomad_link/mcp/liftover_select.py` and import it in both files.)

- [ ] **Step 4: Run the test to confirm it now PASSES**

Run: `uv run pytest tests/unit/mcp/test_compare_variant.py -v`
Expected: PASS — fixed code resolves GRCh37 to `source` (`17-7577121-G-A`), queries r2_1 with it, leg is `present:true`.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/mcp/test_compare_variant.py gnomad_link/mcp/tools/comparison.py
git commit -m "fix(mcp): compare_variant lifts r2_1 leg to GRCh37 (was false present:false)"
```

### Task 3: Add a dedicated regression test mirroring the real HFE case

**Files:**
- Modify: `tests/unit/mcp/test_compare_variant.py` (add one test)

- [ ] **Step 1: Add the regression test** (uses HFE C282Y-shaped coords; asserts the lifted id is distinct from the GRCh38 input):

```python
@pytest.mark.asyncio
async def test_compare_r2_1_uses_grch37_source_not_input_coordinate() -> None:
    """Regression: the r2_1 leg must use the GRCh37 `source` id, not the GRCh38 input."""
    from gnomad_link.mcp.facade import create_gnomad_mcp

    stub = _StubService(
        freq_by_dataset={
            "gnomad_r4": _freq("6-26092913-G-A", "gnomad_r4"),
            "gnomad_r2_1": _freq("6-26093141-G-A", "gnomad_r2_1"),
        },
        liftover_result=[
            {
                "source": {"variant_id": "6-26093141-G-A", "reference_genome": "GRCh37"},
                "liftover": {"variant_id": "6-26092913-G-A", "reference_genome": "GRCh38"},
                "datasets": ["gnomad_r2_1", "gnomad_r4"],
            }
        ],
    )
    mcp = create_gnomad_mcp(service_factory=lambda: stub)

    result = await mcp.call_tool(
        "compare_variant_across_datasets",
        {"variant_id": "6-26092913-G-A", "datasets": ["gnomad_r4", "gnomad_r2_1"], "auto_liftover": True},
    )
    payload = _structured(result)

    assert payload["datasets"]["gnomad_r2_1"]["present"] is True
    assert ("6-26093141-G-A", "gnomad_r2_1") in stub.freq_calls
    assert ("6-26092913-G-A", "gnomad_r2_1") not in stub.freq_calls
    assert any("6-26093141-G-A" in note for note in payload["build_notes"])
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/unit/mcp/test_compare_variant.py::test_compare_r2_1_uses_grch37_source_not_input_coordinate -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/mcp/test_compare_variant.py
git commit -m "test(mcp): regression for compare r2_1 GRCh37 liftover coordinate"
```

### Task 4: Add a live integration test

**Files:**
- Create/modify: a test in `tests/integration/` (follow the existing integration test pattern there)

- [ ] **Step 1: Add an `integration`-marked live test** asserting HFE C282Y resolves in r2_1 via compare:

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_compare_finds_hfe_c282y_in_r2_1_live() -> None:
    from gnomad_link.mcp.facade import create_gnomad_mcp
    from gnomad_link.services.frequency_service import FrequencyService  # adjust to real factory

    mcp = create_gnomad_mcp()  # real service factory per existing integration tests
    result = await mcp.call_tool(
        "compare_variant_across_datasets",
        {"variant_id": "6-26092913-G-A", "datasets": ["gnomad_r4", "gnomad_r2_1"], "auto_liftover": True},
    )
    payload = _structured(result)
    r2 = payload["datasets"]["gnomad_r2_1"]
    assert r2["present"] is True
    assert r2.get("lifted_variant_id") == "6-26093141-G-A"
```

(Match the real construction/helpers used by existing `tests/integration/` tests; do not invent a factory.)

- [ ] **Step 2: Run live (manual)**

Run: `make test-integration` (or `uv run pytest tests/integration -k hfe_c282y -m integration -v`)
Expected: PASS against live gnomAD (skip if API rate-limited).

- [ ] **Step 3: `make ci-local` and commit**

Run: `make ci-local`
Expected: green (integration test excluded from default path).

```bash
git add tests/integration/
git commit -m "test(mcp): live integration for compare HFE C282Y r2_1 presence"
```

**Phase 1 acceptance:** corrected fixture went red then green; new regression passes; `make ci-local` green; live integration confirms r2_1 presence.

---

## Phase 2 — Eval harness + baseline (the gate)

Two harnesses (see spec). **2a is deterministic and wired into `ci-local`**; 2b is optional/live. Build 2a fully; scaffold 2b.

### Task 5: Deterministic eval harness skeleton (`tests/eval/`)

**Files:**
- Create: `tests/eval/__init__.py`, `tests/eval/fixtures.py`, `tests/eval/scenarios.py`, `tests/eval/scoring.py`, `tests/eval/test_eval_baseline.py`

- [ ] **Step 1: `fixtures.py`** — recorded gnomAD responses via `respx` + canned JSON. Reuse the JSON shapes already asserted in `tests/unit/mcp/` (e.g. the `_freq` shapes, gene/SV/mito payloads). One `respx` router fixture that maps the gnomAD GraphQL endpoint to canned responses keyed by the scenario's variant/gene. No network.

- [ ] **Step 2: `scenarios.py`** — a list of `Scenario` dataclasses, each with: `name`, an ordered list of `(tool_name, arguments)` calls, the `expected_tools` set, a `trajectory_mode` (`EXACT`/`IN_ORDER`/`ANY_ORDER`), and `correctness_assertions` (callables over the final payload). Encode the 5 scenarios from the spec:
  - `carrier_frequency_hfe` — `compute_gene_carrier_frequency(gene_symbol="HFE")`
  - `compare_c282y` — `compare_variant_across_datasets("6-26092913-G-A")`; assert r2_1 `present:true`
  - `mito_m3243ag_evidence` — `get_mitochondrial_variant` + `get_clinvar_variant_details`; assert evidence fields present (NOT a pathogenicity verdict)
  - `g6pd_xl_carrier` — `resolve_variant_id` -> `compute_carrier_frequency(inheritance="XL")`; assert afr female-carrier ~0.262 band
  - `grin2b_lof` — `get_gene_variants(consequence="stop_gained")`; assert count consistent with `obs_lof`

- [ ] **Step 3: `scoring.py`** — three scorers returning 0-10 per dimension:
  - `score_trajectory(actual_calls, scenario)` — set/order match per `trajectory_mode`
  - `score_token_cost(payloads)` — measured `len(json.dumps(payload))` per call; scored against a per-scenario byte budget recorded in the baseline
  - `score_envelope_conformance(payload, tool)` — asserts the Success-envelope contract (spec): `_meta.unsafe_for_clinical_use is True`, `_meta.gnomad_release` present, `_meta.next_commands` is a non-empty list of `{tool, arguments}` with non-empty `arguments`, and `headline` present for headline tools.
  - `aggregate(scores) -> Scorecard` — per-dimension + weighted total.

- [ ] **Step 4: `test_eval_baseline.py`** — a pytest module (deterministic, default CI) that runs every scenario through the in-process MCP (`create_gnomad_mcp(service_factory=...)` against the `respx` fixtures), scores them, writes/loads the baseline snapshot, and asserts `total >= baseline.total` (no regression). On first run, write the baseline.

- [ ] **Step 5: Run it**

Run: `uv run pytest tests/eval -v`
Expected: PASS; baseline scorecard produced.

- [ ] **Step 6: Commit**

```bash
git add tests/eval/
git commit -m "test(eval): deterministic MCP eval harness (trajectory/token/conformance)"
```

### Task 6: Wire `eval-ci` into `ci-local`; scaffold `eval-live`; commit baseline

**Files:**
- Modify: `Makefile` (add `eval-ci`, `eval-live`; add `eval-ci` to `ci-local`)
- Create: `docs/superpowers/eval-baseline-2026-05-31.md`

- [ ] **Step 1: Add Make targets** (mirror existing `test-*` style):

```makefile
eval-ci: ## Run deterministic MCP eval harness (no network)
	uv run pytest tests/eval -m "not integration" -q

eval-live: ## Run agentic/live eval against real gnomAD (manual)
	uv run pytest tests/eval -m integration -q
```

- [ ] **Step 2: Add `eval-ci` to `ci-local`** — change the `ci-local` recipe line to:

```makefile
ci-local: format-check lint-ci lint-loc typecheck-fast test-fast eval-ci ## Run fast local CI-equivalent checks
```

- [ ] **Step 3: Write the baseline scorecard** to `docs/superpowers/eval-baseline-2026-05-31.md` (per-dimension + total from Task 5's run; map the 8 reviewer dimensions to the captured numbers).

- [ ] **Step 4: Verify**

Run: `make ci-local`
Expected: green, including `eval-ci`.

- [ ] **Step 5: Commit**

```bash
git add Makefile docs/superpowers/eval-baseline-2026-05-31.md
git commit -m "build(eval): wire eval-ci into ci-local; commit baseline scorecard"
```

- [ ] **Step 6 (optional, 2b scaffold):** add a `tests/eval/test_eval_agentic.py` marked `@pytest.mark.integration` that runs a real-model loop and scores final-answer quality (LLM-as-judge). Opt-in only; skipped without model credentials. Commit separately.

**Phase 2 acceptance:** `make eval-ci` runs deterministically inside `ci-local`; baseline committed; `eval-live` target exists.

---

## Phase 3 — Contract consistency (finish G5)

Make `_meta.next_commands` structured-and-present on every success, and error fallbacks executable.

### Task 7: Shared `next_commands` builders

**Files:**
- Create: `gnomad_link/mcp/next_commands.py`

- [ ] **Step 1:** Add typed builders so every tool emits the same shape, e.g.:

```python
from typing import Any


def cmd(tool: str, **arguments: Any) -> dict[str, Any]:
    """One next_commands entry. Arguments must be directly callable (never empty)."""
    return {"tool": tool, "arguments": arguments}


def for_variant(variant_id: str, dataset: str) -> list[dict[str, Any]]:
    return [
        cmd("get_variant_frequencies", variant_id=variant_id, dataset=dataset),
        cmd("get_clinvar_variant_details", variant_id=variant_id),
    ]
```

- [ ] **Step 2:** Unit test `tests/unit/mcp/test_next_commands.py` asserting each builder returns non-empty `arguments`. Run, then commit.

```bash
git add gnomad_link/mcp/next_commands.py tests/unit/mcp/test_next_commands.py
git commit -m "feat(mcp): shared next_commands builders"
```

### Task 8: Convert `resolve_variant_id` / `search_variants` to structured next_commands

**Files:**
- Modify: `gnomad_link/mcp/tools/search.py:255-268` and `:337-344`

- [ ] **Step 1: Write the failing test** in `tests/unit/mcp/` asserting `resolve_variant_id` success payload has `_meta.next_commands[0] == {"tool": "get_variant_frequencies", "arguments": {"variant_id": <top hit>, "dataset": <dataset>}}` and still carries `next_steps` (deprecated). Run; expect FAIL.

- [ ] **Step 2: Implement** — in `resolve_variant_id.call()` (`:255-262`), keep `next_steps` and add `_meta.next_commands` built from `results[0]["variant_id"]` when results exist:

```python
            payload: dict[str, Any] = {
                "results": results,
                "returned": len(results),
                "next_steps": [
                    "Pick one variant_id and call get_variant_frequencies(variant_id, dataset).",
                    "Or call get_variant_details(variant_id, dataset) for annotations.",
                ],
            }
            meta: dict[str, Any] = {}
            if results:
                meta["next_commands"] = for_variant(results[0]["variant_id"], dataset)
            if enrichment_failures > 0:
                meta["enrichment_partial"] = True
                meta["enrichment_failures"] = enrichment_failures
            if meta:
                payload["_meta"] = meta
            return payload
```

Apply the same to `search_variants.call()` (`:337-344`), merging into its existing `_meta` dict. Add `from gnomad_link.mcp.next_commands import for_variant` import.

- [ ] **Step 3:** Run the test; expect PASS. Commit.

```bash
git add gnomad_link/mcp/tools/search.py tests/unit/mcp/
git commit -m "feat(mcp): structured next_commands on resolve_variant_id/search_variants"
```

### Task 9: Add next_commands to variant_details / structural_variant / gene_variants; unconditional for mito/transcript

**Files:**
- Modify: `gnomad_link/mcp/tools/variants.py` (`get_variant_details`), `gnomad_link/mcp/tools/specialty.py` (`get_structural_variant`, `get_mitochondrial_variant`, `get_transcript_details`), `gnomad_link/mcp/tools/genes.py` (`get_gene_variants`)

- [ ] **Step 1:** Write per-tool tests asserting each success payload carries a non-empty `_meta.next_commands`. Run; expect FAIL for the tools currently omitting it.

- [ ] **Step 2:** Add `_meta.next_commands` to each:
  - `get_variant_details` -> `for_variant(variant_id, dataset)`
  - `get_structural_variant` -> `[cmd("search_structural_variants", gene_symbol=<mate gene or input>), cmd("get_region", region=<sv region>)]`
  - `get_gene_variants` -> `[cmd("get_gene_details", gene_symbol=symbol), cmd("get_clinvar_variant_details", variant_id=<first hit>)]`
  - `get_mitochondrial_variant` / `get_transcript_details` -> make the existing conditional emission unconditional (provide a default chain to `get_server_capabilities`/`get_gene_details` when gene context is absent).

- [ ] **Step 3:** Run tests; expect PASS. Commit.

```bash
git add gnomad_link/mcp/tools/variants.py gnomad_link/mcp/tools/specialty.py gnomad_link/mcp/tools/genes.py tests/unit/mcp/
git commit -m "feat(mcp): universal next_commands on detail/SV/gene-variants/mito/transcript"
```

### Task 10: Executable error fallback args

**Files:**
- Modify: `gnomad_link/mcp/errors.py:54-63` (`McpErrorContext`), `:146-147` (`_fallback_for`); `gnomad_link/mcp/tools/search.py:273,349`

- [ ] **Step 1: Write the failing test** asserting a `resolve_variant_id` not_found/invalid_input envelope has `_meta.next_commands[0] == {"tool": "search_genes", "arguments": {"query": <original query>}}` (not `{}`). Run; expect FAIL.

- [ ] **Step 2: Implement** — add `query: str | None = None` to `McpErrorContext`:

```python
@dataclass
class McpErrorContext:
    tool_name: str
    variant_id: str | None = None
    gene_id: str | None = None
    gene_symbol: str | None = None
    region: str | None = None
    dataset: str | None = None
    query: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
```

Change `_fallback_for` (`:146-147`):

```python
    if context.tool_name in {"resolve_variant_id", "search_variants"}:
        return "search_genes", ({"query": context.query} if context.query else None)
```

Populate the context at the two call sites (`search.py:273` and `:349`):

```python
        context=McpErrorContext(tool_name="resolve_variant_id", query=query),
```
```python
        context=McpErrorContext(tool_name="search_variants", query=query),
```

- [ ] **Step 3:** Run the test; expect PASS. Commit.

```bash
git add gnomad_link/mcp/errors.py gnomad_link/mcp/tools/search.py tests/unit/mcp/
git commit -m "fix(mcp): populate executable query in resolve/search error fallback"
```

### Task 11: Update capabilities contract text + re-score

**Files:**
- Modify: `gnomad_link/mcp/resources.py:226-230`

- [ ] **Step 1:** Update the `next_commands` contract description so it truthfully states it is present (structured) on success and error envelopes for all tools.
- [ ] **Step 2:** Run `make eval-ci`; confirm the envelope-conformance dimension is 100% and total >= baseline. Update the baseline doc if improved.
- [ ] **Step 3: `make ci-local` + commit**

```bash
git add gnomad_link/mcp/resources.py docs/superpowers/eval-baseline-2026-05-31.md
git commit -m "docs(mcp): capabilities reflects universal next_commands contract"
```

**Phase 3 acceptance:** envelope-conformance = 100% in `eval-ci`; `make ci-local` green.

---

## Phase 4 — Token efficiency

### Task 12: `response_mode='minimal'` per-tool (4a)

**Files:**
- Create: `gnomad_link/mcp/minimal_shaping.py`
- Modify: `gnomad_link/mcp/tools/{variants,genes,gene_summary,carrier,gene_carrier,comparison}.py`

- [ ] **Step 1:** In `minimal_shaping.py`, add one projection per tool reading that tool's headline-source fields (see the spec's Phase-4 table for exact field lists). Each returns `{headline, <global block>, _meta}` and a `truncated` block with `to_restore: "response_mode='compact'"`. Keep the full `_meta` (provenance + next_commands) and the research-use flag — minimal must not drop groundability.

- [ ] **Step 2:** For `get_variant_frequencies` (`variants.py:48`), **add** a `response_mode` param `Literal["compact", "full", "minimal"]` defaulting to `"compact"` (current behavior). For the other five tools, **extend** the existing `Literal["compact", "full"]` to include `"minimal"`. Route `response_mode == "minimal"` through the new projection.

- [ ] **Step 3:** Per-tool tests asserting `minimal` returns only the headline + global block + `_meta` (no per-pop/contributing arrays) and that `compact`/`full` are byte-for-byte unchanged. Run; expect PASS.

- [ ] **Step 4: `make eval-ci`** — confirm the token-cost dimension drops for the top-line scenarios; update baseline. Commit.

```bash
git add gnomad_link/mcp/minimal_shaping.py gnomad_link/mcp/tools/ tests/unit/mcp/ docs/superpowers/eval-baseline-2026-05-31.md
git commit -m "feat(mcp): response_mode='minimal' for headline tools"
```

### Task 13: SV/mito compact trimming — domain-specific (4b)

**Files:**
- Modify: `gnomad_link/mcp/sv_shaping.py` (`shape_structural_variant`), `gnomad_link/mcp/heteroplasmy.py` (`shape_mitochondrial_variant`)

- [ ] **Step 1: Write failing tests.** SV: under `compact`, populations with `ac == 0` and `_XX`/`_XY` rows are dropped while `homozygote_count`/`hemizygote_count` survive on kept rows. Mito: rows with `ac_het == 0 and ac_hom == 0` and `_XX`/`_XY` and all-zero haplogroup rows are dropped. Both emit a `truncated` block. Run; expect FAIL.

- [ ] **Step 2: Implement separate projections** (do NOT call SNV `filter_populations`, which keys on `ac`):
  - SV: filter `populations` on `(p.get("ac") or 0) > 0` and `not is_sex_split(p["id"])`; preserve all other fields.
  - Mito: filter on `(p.get("ac_het") or 0) > 0 or (p.get("ac_hom") or 0) > 0`, drop sex-split and all-zero haplogroup rows. Reuse `population_shaping.is_sex_split` for the sex-split test only.
  - Emit `truncated` blocks; correct the `token_cost_hints` for both tools.

- [ ] **Step 3:** Run tests; expect PASS. `make eval-ci`; commit.

```bash
git add gnomad_link/mcp/sv_shaping.py gnomad_link/mcp/heteroplasmy.py tests/unit/mcp/
git commit -m "perf(mcp): trim zero-AC/sex-split rows in SV and mito compact mode"
```

**Phase 4 acceptance:** `minimal` shapes verified; SV/mito trimming verified (incl. mito `ac_het`/`ac_hom` rule); measured token reduction in `eval-ci`.

---

## Phase 5 — Docs + Gemini interop (polish)

### Task 14: Doc-string and capabilities corrections

**Files:**
- Modify: `gnomad_link/mcp/tools/metadata.py:40`, `gnomad_link/mcp/resources.py` (concurrency note)

- [ ] **Step 1:** `metadata.py:40` — change `"Returns <2kB."` to `"Returns ~7kB."` (match `resources.py:105`).
- [ ] **Step 2:** In `resources.py`, extend the concurrency note: `compare_variant_across_datasets` issues ~4 *sequential* upstream calls per invocation (one per dataset + the r2_1 liftover), so N concurrent `compare` calls consume N slots continuously.
- [ ] **Step 3:** If a unit test asserts the `metadata` description text, update it. Run `make test-fast`; commit.

```bash
git add gnomad_link/mcp/tools/metadata.py gnomad_link/mcp/resources.py tests/
git commit -m "docs(mcp): fix capabilities size hint and compare concurrency note"
```

### Task 15: README + MCP connection guide (tool count, Gemini interop)

**Files:**
- Modify: `README.md:20` and the "Available MCP Tools" table at `:139`; the MCP connection guide under `docs/`

- [ ] **Step 1:** Update `README.md:20` `"15 MCP Tools"` -> the current count (22) and refresh the `:139` tool table to the full inventory.
- [ ] **Step 2:** In the MCP connection guide, add a Gemini hosted-MCP section: a `name: "gnomad_link"` (snake_case) example (the server name is client-supplied; dashes are rejected by Gemini), a note that the server serves Streamable HTTP, and an `allowed_tools` example selecting a focused sub-set (<=10-20) for Gemini agents. Document the tool categories and that deferred-loading/tool-search mitigates the 22-vs-10-20 gap.
- [ ] **Step 3:** `make ci-local`; commit.

```bash
git add README.md docs/
git commit -m "docs: refresh tool count to 22; add Gemini hosted-MCP connection guidance"
```

### Task 16: Final scorecard + milestone check

- [ ] **Step 1:** Run `make eval-ci`; capture the final scorecard.
- [ ] **Step 2:** Confirm the "9.5" bar (spec): compare-bug correctness = pass; envelope-conformance = 100%; measured token reduction; zero regressions; total >= 9.4.
- [ ] **Step 3:** Update `docs/superpowers/eval-baseline-2026-05-31.md` with the before/after totals. `make ci-local` green. Commit.

```bash
git add docs/superpowers/eval-baseline-2026-05-31.md
git commit -m "docs(eval): final 9.5 scorecard (before/after)"
```

**Phase 5 acceptance:** docs accurate; final scorecard >= 9.4; `make ci-local` green.

---

## Self-Review

- **Spec coverage:** P1 covers finding #1 (Tasks 1-4). P2 builds the harness (Tasks 5-6). P3 covers findings #3+#4 (Tasks 7-11). P4 covers finding #5 + minimal mode (Tasks 12-13). P5 covers findings #2+#6 + README #9 + Gemini interop (Tasks 14-16). All spec sections mapped.
- **No placeholders:** exact files, line numbers, code, and commands throughout; field lists for minimal projections reference the spec's Phase-4 table (defined, not "TBD").
- **Type consistency:** `select_build_variant_id(record, target_build)` used identically in Tasks 1-2; `cmd(...)`/`for_variant(...)` from `next_commands.py` used in Tasks 7-9; `McpErrorContext.query` added in Task 10 and consumed in `_fallback_for`.
- **Open execution-time reads:** the harness fixtures (Task 5) and minimal projections (Task 12) require reading the corresponding shaping modules for exact field plumbing — the spec's Phase-4 table and the Success-envelope contract fix the contract so no invention is needed.
