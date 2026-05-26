# MCP Facade Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the 12 remaining gaps identified in `docs/mcp-llm-consumer-review.md` and the second-pass deep audit against the committed feat branch. After this plan ships, every tool in the suite follows the same shape conventions the headline `get_variant_frequencies` tool already obeys (truncated metadata with `to_disable`/`to_restore`, cross-link `next_commands`, structured summaries, response_mode for heavy payloads), and the server actively prevents the highest-leverage silent failure mode (coordinate-build / dataset mismatch).

**Architecture:** Surgical edits on top of the hand-authored facade landed by `2026-05-25-mcp-facade-migration.md`. No new top-level packages; new behavior layers onto existing modules (`gnomad_link/mcp/shaping.py`, `gnomad_link/mcp/tools/*.py`, `gnomad_link/mcp/errors.py`, `gnomad_link/mcp/resources.py`). No new tools (Phase C in the review is deferred). Service layer gets one helper for build-mismatch detection.

**Tech Stack:** Python 3.12, FastMCP (already wired), Pydantic v2 (`Annotated` + `Field` + `model_validator`), pytest, pytest-asyncio, Ruff, mypy.

**Standards reference:**
- Anthropic MCP spec 2025-06-18 (ToolAnnotations, output schemas, resource audiences, structured errors).
- Google AIP-157 (partial responses / FieldMask) for response_mode.
- Google AIP-217 (unreachable resources) for build-mismatch detection.
- Google AIP-132 (list pagination) for ClinVar submissions limit.

---

## Pre-Flight Reading

Before starting Task A1, the executor must read these files (already in repo):

- `gnomad_link/mcp/shaping.py` — pattern source for `to_disable`/`to_restore` truncation
- `gnomad_link/mcp/tools/variants.py` — headline tool implementation
- `gnomad_link/mcp/tools/genes.py` — gene tool implementation
- `gnomad_link/mcp/tools/clinvar.py` — ClinVar tool implementation
- `gnomad_link/mcp/tools/search.py` — search/resolve tool implementation
- `gnomad_link/mcp/tools/coordinates.py` — region + liftover implementation
- `gnomad_link/mcp/tools/specialty.py` — SV/mitochondrial/transcript implementation
- `gnomad_link/mcp/errors.py` — `run_mcp_tool`, `McpErrorContext`, structured envelopes
- `gnomad_link/mcp/resources.py` — capabilities resource shape
- `gnomad_link/services/frequency_service.py` — service wrappers
- `gnomad_link/models/variant_models.py` — Pydantic response models
- `docs/mcp-llm-consumer-review.md` — review with 15 action items

---

## Invariants (must hold across every task)

- Each task must be a single atomic commit on `feat/mcp-facade-migration`. Commit subject in the form: `feat(mcp): <one-line summary>` or `refactor(mcp): ...` or `chore(mcp): ...`.
- Every task starts with a failing test (TDD). Step 1 of every task is "write the failing test first".
- No raise of `.loc-allowlist` ceilings. If a module approaches 600 lines, split per project rule.
- No widening of mypy / ruff ignore lists. Fix the underlying issue.
- No new live integration tests in `tests/unit/`. Live tests go to `tests/integration/` only.
- `make ci-local` must pass at the end of every task.
- Existing MCP tool names and response shapes do not change in a breaking way. New fields are additive; deprecations carry `_meta.deprecated`.
- Research-use safety meta (`_meta.unsafe_for_clinical_use: True`) is preserved on every success and error response (already injected by `run_mcp_tool`; do not remove).

---

## Final Tool Surface

No new tools. No removed tools. Existing 16 tools gain richer behavior:

| Tool | Phase A | Phase B | Phase D |
|---|---|---|---|
| `get_variant_frequencies` | + `next_commands` → ClinVar (A2) | + build_mismatch precheck (B1) + freshness (B2) | + token-cost hint (D1) |
| `get_variant_details` | + tightened schema (A3) + truncated (A1) + canonical_transcript (A4) | + freshness (B2) | + token-cost hint (D1) |
| `get_gene_details` | + response_mode=compact (A4) + truncated (A1) | + freshness (B2) | + token-cost hint (D1) |
| `get_gene_variants` | unchanged | + freshness (B2) | unchanged |
| `get_clinvar_variant_details` | + truncated (A1) | + submissions summary + pagination (B3) + freshness (B2) | unchanged |
| `get_clinvar_meta` | unchanged | + freshness (B2) | + deprecation alias notice (D2) |
| `liftover_variant` | unchanged | + `source_genome` param rename with alias (B4) | unchanged |
| `get_structural_variant` | + tightened schema (A3) | + freshness (B2) | + token-cost hint (D1) |
| `get_mitochondrial_variant` | + alias normalization (A5) | + freshness (B2) | unchanged |
| `get_region` | + tightened schema (A3) | + freshness (B2) | unchanged |
| `get_transcript_details` | unchanged | + freshness (B2) | unchanged |
| `search_genes` | + match_quality ranking (A6) | unchanged | + token-cost hint (D1) |
| `resolve_variant_id` | unchanged | + `{gene, consequence, af}` enrichment (B4) | unchanged |
| `search_variants` (alias) | unchanged | + same enrichment via delegate (B4) | unchanged |
| `get_server_capabilities` | unchanged | + clinvar_release_date + gnomad_release (D2) | + capabilities sync test (D1) |
| `get_gnomad_diagnostics` | unchanged | unchanged | unchanged |

---

## Phase A — Consistency Hardening

### Task A1: Propagate `truncated.{to_disable, to_restore}` to remaining tools

**Files:**
- Modify: `gnomad_link/mcp/shaping.py`
- Modify: `gnomad_link/mcp/tools/variants.py`
- Modify: `gnomad_link/mcp/tools/genes.py`
- Modify: `gnomad_link/mcp/tools/clinvar.py`
- Create: `tests/unit/mcp/test_truncated_propagation.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/mcp/test_truncated_propagation.py` with:

- `test_variant_details_compact_emits_truncated_when_transcripts_dropped` — feed a raw payload with 50 transcript_consequences and assert the compact-mode response includes `truncated.kind == "transcript_consequences"`, `truncated.dropped` count, and `truncated.to_restore == "response_mode='full'"`.
- `test_gene_details_compact_emits_truncated_when_present` — feed a raw `Gene` dict with `transcripts` and `exons` arrays; assert compact-mode strips them and emits `truncated.kind == "gene_payload"` with `to_restore == "response_mode='full'"`.
- `test_clinvar_submissions_emit_truncated_when_capped` — feed a payload with 30 submissions; assert the response includes `truncated.kind == "submissions"`, `truncated.dropped == 25` (default cap = 5 for the test), and `truncated.to_disable == "raise submissions_limit (max 200)"`.

Run `make test-unit` and confirm all three fail.

- [ ] **Step 2: Add shaping helpers**

In `gnomad_link/mcp/shaping.py`, add:

```python
def shape_gene_details_compact(raw: dict[str, Any]) -> dict[str, Any]:
    """Project a Gene payload to constraint + canonical transcript + coordinates.

    Drops heavy arrays (transcripts, exons, alt_transcripts) and emits a
    truncated block so the LLM can request the full payload with response_mode='full'.
    """
    heavy_keys = {"transcripts", "exons", "alt_transcripts"}
    dropped = {k: len(raw.get(k) or []) for k in heavy_keys if raw.get(k)}
    compact = {k: v for k, v in raw.items() if k not in heavy_keys}
    if any(dropped.values()):
        compact["truncated"] = {
            "kind": "gene_payload",
            "dropped": dropped,
            "to_disable": "response_mode='full' returns the full payload",
            "to_restore": "response_mode='full'",
        }
    return compact


def shape_clinvar_submissions(
    payload: dict[str, Any], *, submissions_limit: int
) -> dict[str, Any]:
    """Cap submissions[] and emit truncated metadata. Mutates a copy of payload."""
    submissions = payload.get("submissions") or []
    if len(submissions) <= submissions_limit:
        return payload
    capped = dict(payload)
    capped["submissions"] = submissions[:submissions_limit]
    capped["truncated"] = {
        "kind": "submissions",
        "dropped": len(submissions) - submissions_limit,
        "filter": {"submissions_limit": submissions_limit},
        "to_disable": "raise submissions_limit (max 200)",
        "to_restore": f"submissions_limit={min(len(submissions), 200)}",
    }
    return capped
```

Also extend `shape_variant_details_compact(raw, *, max_transcripts=10)` so it accepts an optional `max_transcripts` int. When `len(raw['transcript_consequences']) > max_transcripts`, keep the first `max_transcripts` (canonical-transcript filter handled in Task A4) and emit `truncated.kind == "transcript_consequences"` with `to_restore == "response_mode='full'"`.

- [ ] **Step 3: Wire shaping into tools**

- In `gnomad_link/mcp/tools/genes.py` `get_gene_details`, add a `response_mode: Literal["compact","full"] = "compact"` param and dispatch through `shape_gene_details_compact` when compact.
- In `gnomad_link/mcp/tools/clinvar.py` `get_clinvar_variant_details`, add a `submissions_limit: int = 25` param (Field with `ge=1, le=200`), and pass payload through `shape_clinvar_submissions` before emitting.
- `variants.py` already calls `shape_variant_details_compact`; just pass `max_transcripts=10` from a new optional param `max_transcripts: int = 10` (Field with `ge=1, le=200`).

- [ ] **Step 4: Verify**

Run `make ci-local`. All three new tests pass. Existing tests still green.

- [ ] **Step 5: Commit**

```
git add gnomad_link/mcp/shaping.py gnomad_link/mcp/tools/variants.py gnomad_link/mcp/tools/genes.py gnomad_link/mcp/tools/clinvar.py tests/unit/mcp/test_truncated_propagation.py
git commit -m "feat(mcp): propagate truncated.to_disable/to_restore to variant_details, gene_details, clinvar"
```

---

### Task A2: Cross-link `_meta.next_commands` on `get_variant_frequencies` → ClinVar

**Files:**
- Modify: `gnomad_link/mcp/tools/variants.py`
- Modify: `tests/unit/mcp/test_frequency_shaping.py` (or new test file)

- [ ] **Step 1: Write failing test**

Add `test_get_variant_frequencies_emits_next_commands_to_clinvar` to `tests/unit/mcp/test_frequency_shaping.py`. Use the existing in-process FastMCP client setup pattern from `test_mcp_facade_surface.py`. Stub the service to return a minimal VariantFrequencyResponse. Assert the result includes `_meta.next_commands` containing a dict `{"tool": "get_clinvar_variant_details", "arguments": {"variant_id": <same id>, "reference_genome": "GRCh38"}}`.

- [ ] **Step 2: Implement**

In `gnomad_link/mcp/tools/variants.py` `get_variant_frequencies`, after `shape_variant_frequencies(...)` returns the dict, attach:

```python
shaped["_meta"] = {
    **(shaped.get("_meta") or {}),
    "next_commands": [
        {
            "tool": "get_clinvar_variant_details",
            "arguments": {
                "variant_id": variant_id,
                "reference_genome": "GRCh38" if dataset in ("gnomad_r3", "gnomad_r4") else "GRCh37",
            },
        },
    ],
}
```

Note: `run_mcp_tool` merges `_meta.unsafe_for_clinical_use` on top of whatever the tool returns; placing `next_commands` here is preserved.

- [ ] **Step 3: Verify + commit**

```
make ci-local
git commit -m "feat(mcp): cross-link get_variant_frequencies to ClinVar via _meta.next_commands"
```

---

### Task A3: Tighten variant ID schema regex across all variant tools

**Files:**
- Modify: `gnomad_link/mcp/tools/variants.py`
- Modify: `gnomad_link/mcp/tools/coordinates.py`
- Modify: `gnomad_link/mcp/tools/specialty.py` (SV only; mitochondrial handled in A5)
- Modify: `tests/unit/mcp/test_mcp_errors.py`

The current pattern is `r"^[^'\"]+$"` which only blocks quote injection. Replace with full grammar:

```python
_VARIANT_ID_PATTERN = r"^([1-9]|1\d|2[0-2]|X|Y|MT?)-\d+-[ACGT]+-[ACGT]+$"
```

This rejects malformed input pre-network with a structured `validation_failed` envelope (already handled by `install_validation_error_handler`).

- [ ] **Step 1: Failing test**

In `tests/unit/mcp/test_mcp_errors.py`, add `test_get_variant_frequencies_rejects_malformed_id`: call the tool with `variant_id="not-a-variant"`. Assert the response is `{success: False, error_code: "validation_failed", field_errors: [{field: "variant_id", reason: <substring "pattern">}]}`.

Also add `test_get_variant_frequencies_rejects_mitochondrial_id`: call with `variant_id="M-7497-G-A"` against `get_variant_frequencies`. Assert validation_failed (because mito belongs in `get_mitochondrial_variant`). Use `MT-` form to test both M/MT — both should fail for the autosomal tool.

- [ ] **Step 2: Implement**

Add the constant at module level in `variants.py`. Apply `pattern=_VARIANT_ID_PATTERN` to:
- `get_variant_frequencies.variant_id`
- `get_variant_details.variant_id`

Apply to `liftover_variant.source_variant_id` in `coordinates.py` (same pattern; both builds use the same grammar).

For `get_structural_variant.variant_id` in `specialty.py`, define a separate pattern: `r"^(DEL|DUP|INS|INV|BND|CPX|CTX|MCNV)_chr([1-9]|1\d|2[0-2]|X|Y|M)_\w+$"`. Use case-insensitive via `Annotated[..., Field(pattern=...)]` with the SV grammar.

- [ ] **Step 3: Verify + commit**

```
make ci-local
git commit -m "refactor(mcp): tighten variant_id schemas to CHROM-POS-REF-ALT grammar"
```

---

### Task A4: Add `response_mode=compact` to `get_gene_details` and canonical-transcript projection to `get_variant_details`

**Note:** Task A1 already adds `response_mode` to `get_gene_details` via `shape_gene_details_compact`. This task layers canonical-transcript filtering on `get_variant_details.shape_variant_details_compact`.

**Files:**
- Modify: `gnomad_link/mcp/shaping.py`
- Modify: `tests/unit/mcp/test_truncated_propagation.py` (already exists from A1)

- [ ] **Step 1: Failing test**

Add `test_compact_keeps_canonical_transcript_first`: feed a payload where `transcript_consequences` includes one item with `canonical: True` (or `mane_select: "NM_xxx"`) somewhere in the middle of the list. Assert the compact output's first transcript is the canonical/MANE one.

Add `test_compact_falls_back_to_first_protein_coding`: feed a payload with no canonical flag but with `biotype: "protein_coding"` on one item. Assert that item is first.

- [ ] **Step 2: Implement**

In `gnomad_link/mcp/shaping.py`, extend `shape_variant_details_compact`:

```python
def _rank_transcript(tx: dict[str, Any]) -> tuple[int, int]:
    # Lower tuple == higher priority. Stable sort across ties.
    if tx.get("canonical") or tx.get("mane_select"):
        return (0, 0)
    if tx.get("biotype") == "protein_coding":
        return (1, 0)
    return (2, 0)


def shape_variant_details_compact(
    raw: dict[str, Any], *, max_transcripts: int = 10
) -> dict[str, Any]:
    ...  # existing keep-set filter
    txs = compact.get("transcript_consequences") or []
    if txs:
        ranked = sorted(enumerate(txs), key=lambda item: (_rank_transcript(item[1]), item[0]))
        compact["transcript_consequences"] = [tx for _, tx in ranked[:max_transcripts]]
        if len(txs) > max_transcripts:
            compact["truncated"] = {
                "kind": "transcript_consequences",
                "dropped": len(txs) - max_transcripts,
                "filter": {"max_transcripts": max_transcripts},
                "to_disable": "response_mode='full' returns every transcript",
                "to_restore": "response_mode='full'",
            }
    return compact
```

- [ ] **Step 3: Verify + commit**

```
make ci-local
git commit -m "feat(mcp): canonical-transcript-first projection in get_variant_details compact mode"
```

---

### Task A5: Mitochondrial alias normalization

**Files:**
- Modify: `gnomad_link/mcp/tools/specialty.py`
- Modify: `tests/unit/mcp/test_mcp_facade_surface.py` (or dedicated specialty test file)

- [ ] **Step 1: Failing test**

Create `tests/unit/mcp/test_specialty_aliases.py`. Add `test_mitochondrial_accepts_chrM_alias`, `test_mitochondrial_accepts_MT_alias`, `test_mitochondrial_accepts_chrMT_alias`: stub the service to capture the variant_id it receives; call with `chrM-7497-G-A`, `MT-7497-G-A`, `chrMT-7497-G-A`. Assert the service is called with `M-7497-G-A` in every case.

- [ ] **Step 2: Implement**

In `gnomad_link/mcp/tools/specialty.py` `get_mitochondrial_variant`:

```python
_MITO_PREFIX_RE = re.compile(r"^(chr)?(M|MT)-", re.IGNORECASE)

def _normalize_mito_id(variant_id: str) -> str:
    return _MITO_PREFIX_RE.sub("M-", variant_id, count=1)
```

Pattern relaxes to `r"^(chr)?(M|MT)-\d+-[ACGT]+-[ACGT]+$"` (case-insensitive via `re.IGNORECASE` would require a model_validator; simpler: extend the regex with both cases). Normalize inside `call()` before passing to `service.get_mitochondrial_variant`.

- [ ] **Step 3: Verify + commit**

```
make ci-local
git commit -m "feat(mcp): accept chrM/MT/chrMT aliases on get_mitochondrial_variant"
```

---

### Task A6: `search_genes` match_quality ranking

**Files:**
- Modify: `gnomad_link/mcp/tools/search.py`
- Modify: `gnomad_link/models/gene_models.py` (add `match_quality` Literal field to `GeneSearchResult`)
- Modify: `tests/unit/mcp/test_mcp_facade_surface.py` (or new test)

- [ ] **Step 1: Failing test**

Create `tests/unit/mcp/test_search_ranking.py`. Stub the service to return three `GeneSearchResult`-shaped dicts for query `"BRCA1"`: one with `symbol="BRCA1"`, one with `gene_id="ENSG00000012048"`, one with `symbol="BRCA1P1"` (pseudogene). Assert:
- All three returned in `results`.
- First result has `match_quality == "exact_symbol"`.
- Second has `match_quality == "exact_ensembl_id"` if query was the Ensembl ID, else `"prefix"`.
- Third has `match_quality == "prefix"` (BRCA1 is a prefix of BRCA1P1).

Add a second test for substring matches (query `"BRC"` matching `BRCA2`): assert `match_quality == "substring"`.

- [ ] **Step 2: Implement**

In `gnomad_link/models/gene_models.py`, add to `GeneSearchResult`:

```python
match_quality: Literal["exact_symbol", "exact_ensembl_id", "prefix", "substring"] | None = None
```

In `gnomad_link/mcp/tools/search.py` `search_genes`, after the service returns hits and before truncation, compute `match_quality` per result against the (upper-cased) query, then sort by `(rank, original_index)` where rank is 0 for exact_symbol, 1 for exact_ensembl_id, 2 for prefix, 3 for substring. Helper:

```python
def _rank_gene_hit(hit: GeneSearchResult, query_upper: str) -> tuple[int, str]:
    sym = (hit.symbol or "").upper()
    gid = (hit.gene_id or "").upper()
    if sym == query_upper:
        return (0, "exact_symbol")
    if gid == query_upper:
        return (1, "exact_ensembl_id")
    if sym.startswith(query_upper):
        return (2, "prefix")
    return (3, "substring")
```

Tag each hit with `match_quality = _rank_gene_hit(hit, q)[1]`.

- [ ] **Step 3: Verify + commit**

```
make ci-local
git commit -m "feat(mcp): rank search_genes hits with match_quality and exact-symbol-first ordering"
```

---

## Phase B — Smart Server Behavior

### Task B1: Build-mismatch detection

This is the single highest-leverage feature in the entire review. When a caller hits `get_variant_frequencies("17-7577121-G-A", dataset="gnomad_r4")`, the position is a GRCh37 coordinate but the dataset is GRCh38 — silently returns 404. Detect this pre-network and return a structured `build_mismatch` envelope pointing to `liftover_variant`.

**Files:**
- Create: `gnomad_link/mcp/build_check.py`
- Modify: `gnomad_link/mcp/tools/variants.py`
- Modify: `gnomad_link/mcp/tools/coordinates.py` (for `get_region`)
- Modify: `gnomad_link/mcp/errors.py` (add `build_mismatch` to `_classify`)
- Create: `tests/unit/mcp/test_build_mismatch.py`

- [ ] **Step 1: Failing tests**

`test_get_variant_frequencies_detects_grch37_against_r4`: call with `variant_id="17-7577121-G-A", dataset="gnomad_r4"`. Assert `error_code == "build_mismatch"`, `retryable == False`, `fallback_tool == "liftover_variant"`, `fallback_args == {"source_variant_id": "17-7577121-G-A", "reference_genome": "GRCh37"}`, recovery contains "liftover" or "GRCh37".

`test_get_variant_frequencies_passes_through_grch38_against_r4`: call with `variant_id="17-7676154-G-A"` (TP53 GRCh38 position). Assert no build_mismatch; service is called.

`test_no_build_check_on_r2_1`: r2_1 is the GRCh37 dataset; calls should bypass the check.

`test_build_check_skipped_on_unknown_chrom`: variant id `chrM-1555-A-G` (mitochondrial) should not trigger a build-mismatch on `gnomad_r4` because mito coords are build-stable.

- [ ] **Step 2: Implement detection**

Create `gnomad_link/mcp/build_check.py`:

```python
"""Heuristic build-mismatch detection for CHROM-POS variant IDs."""

from __future__ import annotations

# GRCh38 chromosome lengths (1-based, inclusive). From ENCODE/UCSC reference.
# Source: https://www.ncbi.nlm.nih.gov/grc/human/data
_GRCH38_LENGTHS = {
    "1": 248_956_422, "2": 242_193_529, "3": 198_295_559, "4": 190_214_555,
    "5": 181_538_259, "6": 170_805_979, "7": 159_345_973, "8": 145_138_636,
    "9": 138_394_717, "10": 133_797_422, "11": 135_086_622, "12": 133_275_309,
    "13": 114_364_328, "14": 107_043_718, "15": 101_991_189, "16": 90_338_345,
    "17": 83_257_441, "18": 80_373_285, "19": 58_617_616, "20": 64_444_167,
    "21": 46_709_983, "22": 50_818_468, "X": 156_040_895, "Y": 57_227_415,
}

_GRCH37_LENGTHS = {
    "1": 249_250_621, "2": 243_199_373, "3": 198_022_430, "4": 191_154_276,
    "5": 180_915_260, "6": 171_115_067, "7": 159_138_663, "8": 146_364_022,
    "9": 141_213_431, "10": 135_534_747, "11": 135_006_516, "12": 133_851_895,
    "13": 115_169_878, "14": 107_349_540, "15": 102_531_392, "16": 90_354_753,
    "17": 81_195_210, "18": 78_077_248, "19": 59_128_983, "20": 63_025_520,
    "21": 48_129_895, "22": 51_304_566, "X": 155_270_560, "Y": 59_373_566,
}


def likely_build(chrom: str, pos: int) -> str | None:
    """Return 'GRCh37', 'GRCh38', or None if ambiguous/unknown.

    The heuristic uses the chromosome-length cutoff that uniquely identifies the
    build. For chromosomes where the lengths overlap (almost all), we return None
    and let the upstream call proceed. Only positions in the GRCh37-only or
    GRCh38-only tail return a definitive build.
    """
    c = chrom.lstrip("chr").upper()
    if c in ("M", "MT", "GL", "KI"):
        return None  # mito and unplaced are build-stable enough
    if c not in _GRCH38_LENGTHS:
        return None
    if pos > _GRCH38_LENGTHS[c] and pos <= _GRCH37_LENGTHS.get(c, 0):
        return "GRCh37"
    if pos > _GRCH37_LENGTHS.get(c, 0) and pos <= _GRCH38_LENGTHS[c]:
        return "GRCh38"
    return None


def dataset_build(dataset: str) -> str:
    return "GRCh37" if dataset == "gnomad_r2_1" else "GRCh38"


def detect_mismatch(variant_id: str, dataset: str) -> str | None:
    """Return mismatched-build name if detected, else None."""
    try:
        chrom, pos_s, _, _ = variant_id.split("-", 3)
        pos = int(pos_s)
    except (ValueError, AttributeError):
        return None
    inferred = likely_build(chrom, pos)
    expected = dataset_build(dataset)
    if inferred and inferred != expected:
        return inferred
    return None
```

Add new exception class to `gnomad_link/mcp/errors.py`:

```python
class BuildMismatchError(ValueError):
    """Raised when a variant ID's coordinate clearly belongs to a different build."""

    def __init__(self, variant_id: str, inferred_build: str, dataset: str):
        self.variant_id = variant_id
        self.inferred_build = inferred_build
        self.dataset = dataset
        super().__init__(
            f"Variant {variant_id} appears to use {inferred_build} coordinates "
            f"but dataset {dataset} uses {_classify_dataset_build(dataset)}."
        )
```

Extend `_classify` in `errors.py`:

```python
if isinstance(exc, BuildMismatchError):
    return "build_mismatch", False, "liftover_variant", {
        "source_variant_id": exc.variant_id,
        "reference_genome": exc.inferred_build,
    }
```

Extend `_recovery_text`:

```python
if error_code == "build_mismatch":
    return (
        "Variant coordinates appear to use a different reference build than "
        "the requested dataset. Run liftover_variant to convert, or switch dataset."
    )
```

- [ ] **Step 3: Wire into tools**

In `variants.py` `get_variant_frequencies.call`:

```python
mismatched = detect_mismatch(variant_id, dataset)
if mismatched:
    raise BuildMismatchError(variant_id, mismatched, dataset)
```

Same in `get_variant_details.call`. In `coordinates.py` `get_region.call`, derive `pos = start` and reuse the same check.

- [ ] **Step 4: Verify + commit**

```
make ci-local
git commit -m "feat(mcp): detect coordinate-build vs dataset mismatch pre-network"
```

---

### Task B2: Freshness metadata `_meta.gnomad_release` on every response

**Files:**
- Modify: `gnomad_link/mcp/errors.py` (extend `run_mcp_tool`)
- Modify: `gnomad_link/mcp/resources.py` (cache the release string)
- Create: `tests/unit/mcp/test_freshness_meta.py`

- [ ] **Step 1: Failing test**

`test_every_success_response_carries_gnomad_release`: parametrize over a handful of tool names; for each, stub the service and assert the result's `_meta.gnomad_release` matches the expected constant (`"4.1.0"` until upstream tells us otherwise — we ship a hardcoded constant, then upgrade to dynamic lookup in a separate task).

`test_error_envelopes_also_carry_gnomad_release`: trigger a validation error; assert `_meta.gnomad_release` is present.

- [ ] **Step 2: Implement**

Add a constant in `gnomad_link/mcp/resources.py`:

```python
GNOMAD_DATA_RELEASE = "4.1.0"  # gnomAD v4.1.0 (released 2024-11)
```

In `gnomad_link/mcp/errors.py`, extend `_RESEARCH_USE_META`:

```python
from gnomad_link.mcp.resources import GNOMAD_DATA_RELEASE

_BASE_META = {
    "unsafe_for_clinical_use": True,
    "gnomad_release": GNOMAD_DATA_RELEASE,
}
```

Replace existing `_RESEARCH_USE_META` references with `_BASE_META` everywhere in `errors.py` (success path in `run_mcp_tool`, `mcp_tool_error`, `mcp_validation_tool_error`).

- [ ] **Step 3: Verify + commit**

```
make ci-local
git commit -m "feat(mcp): inject _meta.gnomad_release on every tool response"
```

---

### Task B3: ClinVar submissions summary

Note: Task A1 added `submissions_limit` and `truncated`. This task adds the structured `summary` aggregation.

**Files:**
- Modify: `gnomad_link/mcp/shaping.py`
- Modify: `gnomad_link/mcp/tools/clinvar.py`
- Modify: `tests/unit/mcp/test_truncated_propagation.py` (extend existing tests)

- [ ] **Step 1: Failing test**

`test_clinvar_emits_submissions_summary`: stub the service to return a payload with submissions like:
```python
[
    {"clinical_significance": "Pathogenic"},
    {"clinical_significance": "Pathogenic"},
    {"clinical_significance": "Likely pathogenic"},
    {"clinical_significance": "Uncertain significance"},
    {"clinical_significance": "Benign"},
]
```
Assert the response includes `summary == {"pathogenic": 2, "likely_pathogenic": 1, "uncertain": 1, "likely_benign": 0, "benign": 1, "other": 0, "conflict": True, "total": 5}`.

Conflict logic: True if both `pathogenic`/`likely_pathogenic` ≥ 1 AND `benign`/`likely_benign` ≥ 1.

- [ ] **Step 2: Implement**

In `gnomad_link/mcp/shaping.py`, add:

```python
def _classify_clinical_significance(sig: str | None) -> str:
    if not sig:
        return "other"
    s = sig.lower()
    if "pathogenic" in s and "likely" in s:
        return "likely_pathogenic"
    if "pathogenic" in s:
        return "pathogenic"
    if "benign" in s and "likely" in s:
        return "likely_benign"
    if "benign" in s:
        return "benign"
    if "uncertain" in s or "vus" in s:
        return "uncertain"
    return "other"


def summarize_clinvar_submissions(submissions: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"pathogenic": 0, "likely_pathogenic": 0, "uncertain": 0,
              "likely_benign": 0, "benign": 0, "other": 0}
    for s in submissions:
        counts[_classify_clinical_significance(s.get("clinical_significance"))] += 1
    pathogenic_side = counts["pathogenic"] + counts["likely_pathogenic"]
    benign_side = counts["benign"] + counts["likely_benign"]
    counts["conflict"] = pathogenic_side > 0 and benign_side > 0
    counts["total"] = len(submissions)
    return counts
```

In `clinvar.py` `get_clinvar_variant_details.call`, after the existing model_dump, before `shape_clinvar_submissions`:

```python
payload["summary"] = summarize_clinvar_submissions(payload.get("submissions") or [])
```

- [ ] **Step 3: Verify + commit**

```
make ci-local
git commit -m "feat(mcp): aggregate ClinVar submissions into pathogenic/benign/uncertain summary"
```

---

### Task B4: Enrich `resolve_variant_id` + rename `liftover_variant.reference_genome` → `source_genome`

Two related polish items in one commit. Both touch the search/coordinates surface.

**Files:**
- Modify: `gnomad_link/mcp/tools/search.py`
- Modify: `gnomad_link/mcp/tools/coordinates.py`
- Modify: `gnomad_link/models/variant_models.py` (extend `VariantSearchResult` with optional fields)
- Modify: `tests/unit/mcp/test_mcp_facade_surface.py`
- Create: `tests/unit/mcp/test_resolve_enrichment.py`

- [ ] **Step 1: Failing tests**

`test_resolve_variant_id_enriches_with_gene_and_consequence`: stub `service.search_variants` to return `["1-55051215-G-GA"]`. Stub `service.get_variant_frequencies` for that ID to return a response with `gene_symbol="PCSK9"`, `major_consequence="frameshift_variant"`, `exome.af=0.0001`. Call `resolve_variant_id(query="rs11591147")`. Assert results contains `{"variant_id": "1-55051215-G-GA", "gene_symbol": "PCSK9", "major_consequence": "frameshift_variant", "af": 0.0001}`.

`test_resolve_variant_id_enrich_disabled_returns_ids_only`: call with `enrich=False`. Assert results have only `variant_id`.

`test_resolve_variant_id_enrichment_failure_does_not_block`: stub the enrichment call to raise. Assert the response still includes results with `variant_id` only and a `_meta.enrichment_partial: True`.

`test_liftover_variant_accepts_source_genome_alias`: call with `source_genome="GRCh37"` instead of `reference_genome="GRCh37"`. Assert the same behavior. Add `test_liftover_variant_emits_deprecation_meta_for_old_name`: call with `reference_genome="GRCh37"`. Assert `_meta.deprecated_params: {"reference_genome": "Use source_genome; will be removed in next release."}`.

- [ ] **Step 2: Implement**

Extend `VariantSearchResult`:

```python
class VariantSearchResult(BaseModel):
    variant_id: str
    gene_symbol: str | None = None
    major_consequence: str | None = None
    af: float | None = None
```

In `search.py` `resolve_variant_id`, add `enrich: bool = True` param (default True per the review). After getting `raw` IDs, for the top `min(limit, 5)`:

```python
enriched: list[dict[str, Any]] = []
errors = 0
for vid in raw[:limit]:
    item = {"variant_id": vid}
    if enrich:
        try:
            freq = await service.get_variant_frequencies(vid, dataset)
            item["gene_symbol"] = freq.gene_symbol
            item["major_consequence"] = freq.major_consequence
            af = None
            if freq.exome:
                af = (freq.exome.allele_count / freq.exome.allele_number) if freq.exome.allele_number else None
            if af is None and freq.genome:
                af = (freq.genome.allele_count / freq.genome.allele_number) if freq.genome.allele_number else None
            item["af"] = af
        except Exception:
            errors += 1
    enriched.append(item)
payload = {"results": enriched, "returned": len(enriched), "next_steps": [...]}
if errors:
    payload["_meta"] = {"enrichment_partial": True, "enrichment_failures": errors}
return payload
```

Apply the same change to the `search_variants` deprecated alias.

In `coordinates.py` `liftover_variant`, add `source_genome: Annotated[Literal["GRCh37", "GRCh38"] | None, Field(...)] = None`. Keep `reference_genome: ... = None` (was required; now optional with same Literal). At runtime:

```python
build = source_genome or reference_genome
if build is None:
    raise ValueError("Provide source_genome (or legacy reference_genome).")
results = await service.liftover_variant(source_variant_id, build)
payload = {...}
if source_genome is None and reference_genome is not None:
    payload["_meta"] = {
        "deprecated_params": {"reference_genome": "Use source_genome; will be removed in next release."},
    }
```

- [ ] **Step 3: Verify + commit**

```
make ci-local
git commit -m "feat(mcp): enrich resolve_variant_id with gene/consequence/af and rename liftover param"
```

---

## Phase D — Polish

### Task D1: Token-cost hints in tool docstrings + capabilities sync test

**Files:**
- Modify: every `gnomad_link/mcp/tools/*.py` (docstrings only)
- Modify: `gnomad_link/mcp/resources.py` (extend capabilities with `token_cost_hints`)
- Modify: `tests/unit/mcp/test_mcp_facade_surface.py`

- [ ] **Step 1: Failing test**

`test_capabilities_resource_lists_token_cost_hints`: assert the capabilities resource exposes a `token_cost_hints` dict keyed by tool name with byte-range strings (e.g. `"get_variant_frequencies": "~2-4kB"`).

`test_capabilities_tools_match_facade_tools` (lock the sync): build a real `create_gnomad_mcp(...)` and assert `set(get_capabilities_resource()["tools"]) == set(mcp._tool_manager._tools.keys())`. This guards against drift.

- [ ] **Step 2: Implement**

In each tool's docstring (one-liner), append a token estimate after the existing description, e.g. for `get_variant_frequencies`: `... Returns ~2-4kB.`. Suggested estimates:
- get_variant_frequencies: ~2-4kB
- get_variant_details: compact ~3kB, full up to ~50kB
- get_gene_details: compact ~2kB, full up to ~30kB
- get_gene_variants: ~5-50kB depending on limit
- get_clinvar_variant_details: ~3-15kB depending on submissions_limit
- get_clinvar_meta: <1kB
- search_genes: ~1-3kB
- resolve_variant_id: ~1-5kB (enrichment dependent)
- liftover_variant: <1kB
- get_region: ~5-50kB
- get_transcript_details: ~5-15kB
- get_structural_variant: ~1-3kB
- get_mitochondrial_variant: ~2-4kB
- get_server_capabilities: <2kB
- get_gnomad_diagnostics: <1kB

In `resources.py`, add `token_cost_hints` dict to `get_capabilities_resource()` mirroring the same values.

- [ ] **Step 3: Verify + commit**

```
make ci-local
git commit -m "chore(mcp): add token-cost hints to tool docstrings + lock tools/capabilities sync"
```

---

### Task D2: Deprecate `get_clinvar_meta`; fold its data into `get_server_capabilities`

**Files:**
- Modify: `gnomad_link/mcp/tools/clinvar.py`
- Modify: `gnomad_link/mcp/tools/metadata.py`
- Modify: `gnomad_link/mcp/resources.py`
- Modify: `tests/unit/mcp/test_mcp_facade_surface.py`

- [ ] **Step 1: Failing test**

`test_capabilities_includes_clinvar_release_date`: assert `get_capabilities_resource()` returns a `clinvar_release_date` key (string or null) and `gnomad_release` key (the constant from B2).

`test_get_clinvar_meta_is_deprecated`: call `get_clinvar_meta()`. Assert response includes `_meta.deprecated: True` and `_meta.use_instead: "get_server_capabilities"`.

- [ ] **Step 2: Implement**

In `clinvar.py`, in `get_clinvar_meta.call`, attach:

```python
result["_meta"] = {
    **(result.get("_meta") or {}),
    "deprecated": True,
    "use_instead": "get_server_capabilities",
    "removal_release": "next minor",
}
```

In `resources.py` `get_capabilities_resource()`, add `"clinvar_release_date": None` (placeholder until a startup probe is added — separate task) and `"gnomad_release": GNOMAD_DATA_RELEASE`.

In `get_server_capabilities` (metadata.py), the tool already wraps `get_capabilities_resource` so it inherits automatically.

- [ ] **Step 3: Verify + commit**

```
make ci-local
git commit -m "chore(mcp): deprecate get_clinvar_meta in favor of get_server_capabilities"
```

---

## Done Criteria

- [ ] Every task above commits cleanly on `feat/mcp-facade-migration`.
- [ ] `make ci-local` green at end of every task and at the end of the plan.
- [ ] `tests/unit/mcp/test_mcp_facade_surface.py::test_capabilities_tools_match_facade_tools` locks tools/capabilities sync.
- [ ] No new `.loc-allowlist` entries; no new ruff/mypy ignores.
- [ ] The 16-tool surface unchanged in name and signature (except for deprecation-aliased liftover param).
- [ ] `docs/mcp-llm-consumer-review.md` action items 1-12 marked done in a follow-up doc edit (outside scope of this plan, but the executor should note it for the user).

---

## Out of Scope (deferred)

Phase C from the review (five new tools: `get_coverage`, `compare_variant_across_datasets`, `compute_carrier_frequency`, `get_gene_summary`, `search_structural_variants`) is intentionally not in this plan. Each of those is a new tool with its own service surface and warrants a separate planning pass.
