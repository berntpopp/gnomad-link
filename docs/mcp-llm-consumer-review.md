# MCP LLM-Consumer Review: Pushing gnomad-link from 8.8 to >9.0

**Date:** 2026-05-26  
**Scope:** Research-only; no source edits.  
**Reference codebase:** pubtator-link `pubtator_link/mcp/`, MCP spec 2025-06-18, FastMCP docs, Anthropic engineering blog, arxiv 2602.14878.

---

## Executive Summary

gnomad-link post-migration already implements the structural skeleton that separates great MCP servers from adequate ones: hand-authored tools, structured error envelopes, output schemas, `ToolAnnotations`, a capabilities resource, and explicit server instructions. The gaps are not architectural — they are a handful of tactical additions concentrated in discoverability, composability, and error-surface hardening. Every item in the prioritised action list below is additive, not structural.

---

## 1. Discoverability (Current: 8/10)

### State of Practice (2026)

The MCP spec 2025-06-18 defines three discoverability surfaces: `tools/list` (schema-level), `resources/list` (reference data), and `prompts/list` (workflow templates). The `server.instructions` field in the `initialize` response is the zero-cost discoverability win: it is injected before tool schemas, costs no extra round-trip, and is the first thing an LLM reads. Claude Desktop, Claude Code, and most hosted integrators splice it into system context automatically.

The spec also defines `completions` capability (`completion/complete` for `ref/prompt` and `ref/resource`), enabling IDE-style argument autocomplete for prompts and resource URI templates. This is new in 2025-06-18 and largely unimplemented outside power-user servers.

The ToolSearch deferred-loading pattern that gnomad-link inherits from Claude Code's hosted environment is a client-side gating decision, not a server design flaw. The server cannot force eager loading. What it *can* control is what the LLM learns before making a ToolSearch call.

### What Pushes Above 9.0

**Structured workflow catalogue in `get_server_capabilities`.** pubtator-link's `resources.py` encodes a `llm_driver_contract` dict with `core_workflow_tools`, `schema_bundle` references, `detail_levels`, and `response_contracts`. This is machine-readable workflow guidance that survives context-window pressure better than prose. gnomad-link's `get_capabilities_resource()` has `recommended_workflows` as a string list but lacks the typed workflow-step structure.

**MCP `prompts` capability.** pubtator-link registers three named prompts (`search_biomedical_literature_prompt`, `review_rerag_workflow_prompt`, `annotate_research_text_prompt`) via FastMCP's `@mcp.prompt` decorator. Prompts appear in `prompts/list` and are retrievable without a `tools/call` round-trip. Claude Desktop and Claude Code surface them as slash commands. For a 15-tool server covering 6 conceptually distinct workflows (frequency lookup, gene constraint, clinical annotation, SV, mito, liftover), prompt-based workflow guidance is exactly the right abstraction.

**`output_cheatsheet` in capabilities.** pubtator-link's resource contains an `output_cheatsheet` mapping human-readable path names (`"single_context_passages"`) to JSON paths (`"context_pack.passages[]"`). LLMs parsing large responses benefit from being told the canonical extraction path before they guess.

### Concrete Techniques for gnomad-link

1. Add a `@mcp.prompt` for each of the 4-5 conceptual workflows (see action list). FastMCP infers the prompt name from the function name and description from the docstring.
2. Upgrade `get_capabilities_resource()` to include an `output_cheatsheet` mapping field names to JSON paths, e.g. `"frequency_populations": "exome.populations[]"`.
3. Add a `llm_driver_contract` sub-dict to the capabilities resource identifying `recommended_entrypoint` (`get_server_capabilities`) and `core_workflow_tools` in order.
4. Add `server_version` and `mcp_protocol_version` fields (already present in gnomad-link; good).

### Anti-Patterns to Avoid

- Putting full JSON schema examples inside the instructions string. Instructions is read at init for routing; schema detail belongs in the tool's `inputSchema`/`outputSchema`.
- Registering prompts with zero arguments that just return a fixed string. Use at least one argument (`topic`, `variant_id`) so the prompt is parameterised and distinguishable from a resource.

### Trade-Offs

Adding MCP prompts increases the server's surface area and adds test obligations. Keep prompts to 4-5 maximum — one per workflow, not one per tool. Do not encode fallback logic in prompts (that belongs in error envelopes).

---

## 2. Schema Clarity (Current: 9/10)

### State of Practice (2026)

The arxiv paper 2602.14878 found 97.1% of MCP tool descriptions contain at least one "smell" — with unstated limitations (89%), missing usage guidelines (85%), and opaque parameters (81%) being the dominant issues. Anthropic's engineering blog (writing-tools-for-agents) distils this to: describe *when* to call the tool (routing), *what* the parameters mean semantically (not just typing), and what the output contains.

The MCP spec 2025-06-18 adds a `title` field to tools (`ToolDefinition.title`) — a human-readable display name separate from the identifier `name`. This is distinct from the tool description. FastMCP exposes it as the `title` parameter in `@mcp.tool()`.

The spec's `inputSchema` supports `description` per property (already used in gnomad-link), `examples` (a JSON Schema keyword), and `default` values. Using `examples` at the property level lets the LLM see a concrete value without having to infer from the description.

### What Pushes Above 9.0

**Property-level `examples` in input schemas.** Every major discriminating field — `variant_id`, `gene_id`, `dataset`, `populations` — should have an `examples` entry showing a real gnomAD value. gnomad-link uses `Field(description=...)` correctly but does not set `examples`. Comparison: pubtator-link's `resources.py` sample_calls dict provides this at the capabilities level; ideally it should also live at the property level in the schema.

**Explicit enum descriptions.** `dataset: Literal["gnomad_r2_1","gnomad_r3","gnomad_r4"]` is correct typing but the Field description just says `"gnomad_r4 default (GRCh38)."` — it doesn't explain that r2_1 is GRCh37 and r3 is GRCh38. The LLM has to reason about this. Add: `description="gnomad_r4 (GRCh38, default), gnomad_r3 (GRCh38, larger WGS), gnomad_r2_1 (GRCh37 legacy)"`.

**Limitations stated inline.** The arxiv paper's strongest finding (89% of tools omit limitations) is the single highest-impact fix for schema clarity. `get_gene_variants` says "Large genes (e.g. TTN) return tens of thousands of variants upstream" — that's good. `get_region` says "cap span at 100kb" — also good. What's missing: `get_variant_frequencies` doesn't state that SV, mito, and gene-within-region queries each need their own dedicated tool.

**Activation criteria.** The "Use this when..." docstring pattern that gnomad-link already enforces is the correct activation guidance structure. The arxiv paper confirms this pattern outperforms pure capability description. gnomad-link's existing test (`test_every_tool_description_leads_with_use_this_when`) is a good enforcement mechanism; keep it.

### Anti-Patterns to Avoid

- Fully augmented descriptions that enumerate all capabilities in the docstring. The arxiv paper found this increases step count by 67% due to LLMs reading more decision branches. Keep docstrings tight: 1 activation sentence + 1 output sentence + max 2 limitation sentences.
- Putting data format specifications (CHROM-POS-REF-ALT format rules) in the docstring rather than in the parameter-level `pattern` and `description`. Both tools already handle this correctly.

### Trade-Offs

Adding `examples` to every field increases the `tools/list` response size. For a 15-tool server this is acceptable. The schema is read once per session; it is not per-call overhead.

---

## 3. Speed (Current: 9/10)

### State of Practice (2026)

Speed for an MCP server is measured at three points: `tools/list` parse time, `tools/call` execution latency, and LLM-side selection overhead (number of tool candidates the LLM must read before choosing). gnomad-link is already fast on the first two by virtue of FastMCP + async.

The third dimension — selection overhead — is controlled by tool count and description density. 15 tools is lean; Anthropic's blog recommends single-digit to low double-digit counts. The namespace is flat (`get_`, `search_`, `liftover_`, `resolve_`) which is good.

### What Pushes Above 9.0

**Tag-based tool categories for host filtering.** FastMCP supports `tags` on tools (`@mcp.tool(tags={"variant", "frequency"})`). Claude Code's `ToolSearch` can filter by tag. Hosts that load a full tool list benefit from tag-based pre-filtering. pubtator-link does not use FastMCP tags (it uses profile-based conditional registration), but for a 15-tool server with fewer cross-cutting concerns, tags are lower cost.

**`mask_error_details=True` is already set.** This prevents large Python traceback strings from being serialised into tool results, which would inflate response tokens and slow LLM processing.

### Concrete Techniques for gnomad-link

Add `tags` to tool registrations: `{"variant"}`, `{"gene"}`, `{"clinical"}`, `{"coordinates"}`, `{"search"}`, `{"metadata"}`. This is a two-character addition per tool with no schema impact.

### Anti-Patterns to Avoid

- Caching the `get_capabilities_resource()` output naively with a long TTL. If dataset availability or tool deprecations change between runs, a stale capabilities resource misleads the LLM. Either compute it fresh per request (fast, correct) or timestamp it.

### Trade-Offs

Tags cost nothing at runtime and marginally increase `tools/list` payload. No meaningful trade-off.

---

## 4. Token Efficiency (Current: 9/10)

### State of Practice (2026)

The "compact default + explicit expansion" pattern is the dominant 2025/2026 practise for token-efficient MCP servers. gnomad-link implements it well: `response_mode="compact"`, `include_subcohorts=False` by default, `exclude_zero_populations=True`. The `truncated` envelope block is the self-documenting mechanism that enables the LLM to re-call with targeted expansion.

The spec's `structuredContent` field (introduced with `outputSchema` in 2025-06-18) means structured results are returned both as a serialised text block and as a machine-parseable JSON object. FastMCP handles this automatically for dict returns when an `outputSchema` is declared. This doubles the information density for clients that consume `structuredContent` — no extra tokens for the LLM, since the client processes it.

The BigData Boutique blog (mistake #6) recommends CSV for tabular data to save 40-60% tokens. For gnomad-link's population frequency arrays, this would be a meaningful saving: instead of `[{"id":"afr","ac":143,"an":8000,"af":0.0178}]` you would emit `id,ac,an,af\nafr,143,8000,0.0178`. However, this breaks outputSchema validation and is not standard MCP practice. The trade-off is real but the recommendation is community-only, not spec-mandated.

### What Pushes Above 9.0

**Per-tool compact summaries.** When `get_variant_frequencies` returns, add a top-level `summary` object with the most important values pre-extracted: `{"overall_af": 0.00178, "max_pop": "afr", "max_pop_af": 0.0178, "has_clinvar": false}`. The LLM can answer most questions from the summary without parsing the full populations array. pubtator-link achieves analogous behaviour via `compact_passages` mode; gnomad-link's shaping module can add this.

**`_meta.next_commands` as structured objects, not strings.** gnomad-link's `errors.py` error envelope emits `"next_commands": ["get_server_capabilities", "gnomad://capabilities"]` — these are strings. pubtator-link emits `"next_commands": [{"tool": "pubtator_diagnostics", "arguments": {}}]` — these are callable argument maps. The structured form lets the LLM construct the next call without parsing a string. This is a 10-line change to `errors.py`.

**`meta_budget` pattern from pubtator-link.** pubtator-link has `meta_budget.py` which strips diagnostic fields before responses are serialised for repeated calls. gnomad-link has no equivalent. For long sessions calling `get_gene_variants` multiple times, the `truncated` block is small enough that this is low priority, but it is a meaningful improvement for `get_region` calls with `include_genes=True` and `include_clinvar=True`.

### Anti-Patterns to Avoid

- Emitting the full raw gnomAD GraphQL response in default mode. The pre-migration server had this bug (silent population truncation). The migration fixed it; do not revert.
- Adding a `verbose` alias for `response_mode="full"`. Having two names for the same mode confuses LLMs (they may pass `verbose=True` as a bool).

### Trade-Offs

Compact summaries require maintenance as gnomAD data schema evolves. The summary fields should be computed from the existing shaped populations data, not from new API fields, to avoid brittleness.

---

## 5. Response Structure (Current: 9/10)

### State of Practice (2026)

The MCP spec 2025-06-18 introduces `structuredContent` alongside the existing `content` text block for tool results. The spec states: "For backwards compatibility, a tool that returns structured content SHOULD also return the serialized JSON in a TextContent block." FastMCP handles the dual emission automatically when `outputSchema` is declared and the tool returns a dict. gnomad-link has `outputSchema` on all data tools — good.

The spec's resource `annotations` object supports `audience: ["user","assistant"]`, `priority: 0.0–1.0`, and `lastModified`. These are hints for the *client* about how to present or filter resources, not for the LLM. Setting `audience: ["assistant"]` on the `gnomad://capabilities` resource signals to UI clients that this resource should be injected into the AI context, not shown to the user.

### What Pushes Above 9.0

**Resource annotations on `gnomad://capabilities` and `gnomad://usage`.** Add `annotations={"audience": ["assistant"], "priority": 1.0}` to the `@mcp.resource` decorator. This costs nothing and signals to compliant clients that these resources are high-priority AI context. FastMCP exposes `annotations` on `@mcp.resource` via the underlying `mcp.types.Resource` object.

**`next_steps` field on every successful response (not just errors).** gnomad-link already does this on `resolve_variant_id` (`"next_steps": ["Pick one variant_id and call get_variant_frequencies..."]`). This pattern should be extended to the other tools. The canonical form from pubtator-link is `_meta.next_commands` as a list of `{tool, arguments}` dicts. Extending this to success responses means the LLM always knows what to call next without back-tracking to the capabilities resource.

**Cross-reference population code descriptions.** `get_variant_frequencies` returns `{"id": "afr", "ac": 143, ...}`. The LLM has to know that `afr` is "African/African-American." Either add a `population_names` lookup table to the capabilities resource, or add a `name` field to shaped population dicts. The capabilities resource already lists codes but not human-readable names.

### Anti-Patterns to Avoid

- Emitting `_meta` in both the top-level response and inside `structuredContent`. The `_meta` convention is MCP-layer metadata; keep it top-level only so it doesn't pollute the schema-validated `structuredContent` object.
- Using `resource_link` content type to point back to `gnomad://capabilities` on every tool response. This adds a round-trip without adding information; the LLM already has the capabilities resource from init.

### Trade-Offs

Adding `_meta.next_commands` to success responses increases every tool call's payload by ~50 bytes. Across 15 tools this is immaterial. The composability benefit is large.

---

## 6. Error Surface / Guardrails (Current: 8/10)

### State of Practice (2026)

The MCP spec defines two error mechanisms: protocol errors (JSON-RPC `-32xxx` codes, for transport-level problems) and tool execution errors (`isError: true` in the result, for domain-level failures). The community consensus pattern, exemplified by pubtator-link, is to return an envelope dict on tool execution failure rather than raising `ToolError` — this way the LLM sees a parseable structured response rather than an opaque error string.

gnomad-link implements this correctly via `run_mcp_tool` returning `exc.payload` on exception. The issue is coverage, not design.

### What Pushes Above 9.0

**Pydantic validation error interception.** pubtator-link installs `install_validation_error_handler(mcp)` in `facade.py` which wraps every registered tool's `run` method to catch `PydanticValidationError` and convert it into the standard envelope before FastMCP converts it to an `isError: true` response. gnomad-link has no equivalent. When a caller passes `dataset="gnomad_r5"`, FastMCP's validation raises `PydanticValidationError` which becomes an unstructured error string. The fix is 30 lines of wrapper code.

**Output schema validation error interception.** pubtator-link has `output_validation.py` which wraps the `CallToolRequest` handler to intercept FastMCP's own output-schema validation failures and convert them into actionable envelopes. This matters when a gnomAD API schema change causes a previously valid response to fail the declared `outputSchema`. gnomad-link has no equivalent.

**Error code taxonomy.** gnomad-link's `errors.py` classifies exceptions into four codes: `not_found`, `validation_failed`, `upstream_unavailable`, `internal_error`. This is correct and sufficient. pubtator-link has additional codes (`review_schema_not_current`, `review_index_unavailable`, `curated_url_rejected`) because it has more failure modes. gnomad-link's taxonomy is appropriate for its domain.

**`retryable` field in error responses.** Already present — correct. This is the primary field LLMs use for branching: retry on `upstream_unavailable`, do not retry on `validation_failed`.

**Missing: field-level validation errors.** When the LLM passes `populations: "afr"` (string instead of list), the error envelope currently says `"error_code": "validation_failed", "message": "Invalid input: ValidationError"`. pubtator-link's `install_validation_error_handler` extracts pydantic field-level errors (`{"field": "populations", "reason": "...", "recovery_hint": "..."}`) from the `PydanticValidationError` and includes them in the envelope. Without this, the LLM cannot self-correct without reading the full tool schema again.

**Sanitisation coverage.** gnomad-link's `_safe_message` truncates to 240 chars and has two safe canned messages. pubtator-link's `sanitize_error_message` has a pattern-matching whitelist that maps raw backend messages to stable public-facing strings. gnomad-link should add pattern matching for common gnomAD upstream errors (rate-limit messages, GraphQL error shapes).

### Anti-Patterns to Avoid

- The BigData Boutique blog mistake #5 is the inverse: do not swallow error details so aggressively that the LLM cannot self-correct. gnomad-link's `_envelope_message` returns `"Internal error: RuntimeError"` for internal errors, which is opaque but safe. This is correct; internal errors should not leak stack details.
- Do not include the raw upstream gnomAD GraphQL error object in the envelope. It can contain large response bodies or user-visible error codes that differ between gnomAD API versions.

### Trade-Offs

Pydantic validation interception adds one wrapper layer per tool. FastMCP's tool internals are not part of its public API; the wrapper technique (`object.__setattr__(tool, "run", wrapped_run)`) is identical to pubtator-link's approach and has worked across multiple FastMCP versions. Monitor for breakage on FastMCP upgrades.

---

## 7. Composability (Current: 8/10)

### State of Practice (2026)

Composability at the MCP level means: given the result of tool A, what is the correct next tool to call, and with what arguments? The two mechanisms are: (1) `_meta.next_commands` embedded in responses, and (2) MCP `prompts` that encode multi-step workflows. A third emerging pattern is using the MCP `sampling` client capability to let the server orchestrate LLM calls internally — this is appropriate for servers that need to perform multi-step agentic work, not for read-only data servers like gnomad-link.

The Anthropic engineering blog recommends consolidating multi-step operations into single tools for common workflows. gnomad-link already does this for liftover (one call, not "convert then query"). The gap is in hinting at the next tool from responses that naturally lead to follow-up calls.

### What Pushes Above 9.0

**`next_commands` as structured call objects on success.** `resolve_variant_id` already emits `"next_steps": ["Pick one variant_id and call get_variant_frequencies(variant_id, dataset)."]` — this is human-readable. The structured form would be:

```json
"_meta": {
  "next_commands": [
    {"tool": "get_variant_frequencies", "arguments": {"variant_id": "{results[0].variant_id}", "dataset": "gnomad_r4"}},
    {"tool": "get_variant_details", "arguments": {"variant_id": "{results[0].variant_id}"}}
  ]
}
```

This is community convention (not spec-mandated) but consistently used by pubtator-link and several Anthropic-example servers. The `{results[0].variant_id}` template form tells the LLM the extraction path explicitly.

**Pair tool annotations in descriptions.** `get_gene_details` says "Follow with get_gene_variants if they then need per-variant rows." This is correct composability guidance. The pattern should be applied to all tools that have natural successors: `get_clinvar_variant_details` → "Pair with get_variant_frequencies for allele counts." `liftover_variant` → "Use the returned CHROM-POS-REF-ALT with get_variant_frequencies in the target build."

**A `get_gnomad_diagnostics` tool.** pubtator-link's `pubtator_diagnostics` tool serves as the universal recovery entry point — it returns recent errors, service health, and environment config. gnomad-link has `get_recent_errors()` and `clear_recent_errors()` in `errors.py` but no MCP-visible diagnostics tool. Adding one (closed-world, `readOnlyHint=True`) would give error envelope `next_commands` a concrete fallback target beyond `get_server_capabilities`.

**Workflow prompts as composability contracts.** Register four MCP prompts: `variant_frequency_workflow`, `gene_constraint_workflow`, `clinical_variant_workflow`, `region_scan_workflow`. Each returns a short instruction string that names the tool sequence in order. Clients that support `prompts/list` (Claude Desktop, Cursor MCP) can expose these as slash commands, enabling one-click workflow initiation.

### Anti-Patterns to Avoid

- Circular `next_commands`: do not list the current tool as a next command in its own success response (this can happen when a tool emits a retry recommendation unconditionally).
- Listing more than 3 `next_commands` items. The LLM reads all of them; past 3, it becomes option paralysis.

### Trade-Offs

`next_commands` in every success response adds ~100 bytes per call. For the token-sensitive case, make `_meta.next_commands` opt-in via an `include_meta: bool = True` parameter (gnomad-link already has `include_meta` on some tools — this pattern should be made consistent).

---

## 8. Self-Documentation (Current: 10/10)

### State of Practice (2026)

The `truncated.to_disable` pattern is gold-standard. The spec has no equivalent prescription, but the pattern appears in Anthropic's example servers and is referenced in the MCP community as the correct way to communicate response shaping decisions. gnomad-link's `shape_variant_frequencies` emits `truncated: {"kind": "populations", "dropped": {"subcohorts": 1, "sex_split": 1, "zero_ac": 1}, "to_disable": "include_subcohorts=True or include_sex_split=True"}`.

This is already at the ceiling for 2026. No structural changes needed.

### Minor Hardening

- Ensure `truncated` appears on *all* shaped responses, not just frequency shaping. `get_gene_variants` and `search_genes` already do this. Confirm `get_region` does as well.
- Add `to_restore` alongside `to_disable` for the inverse: which parameter restores the dropped data. The distinction matters when both the `populations` filter and `exclude_zero_populations` are active simultaneously.

### Anti-Patterns to Avoid

- Emitting `truncated` even when nothing was dropped (`truncated: null` or `truncated: {dropped: {subcohorts: 0, sex_split: 0}}`). Null/empty truncated blocks waste tokens. Only emit the field when at least one row was dropped.

---

## 9. Research-Scope Clarity (Current: 9/10)

### State of Practice (2026)

Research-scope restrictions appear at four levels in well-designed servers: (1) server `instructions` string, (2) capabilities resource `research_use_only: true` flag, (3) per-tool `unsafe_for_clinical_use: true` in `_meta`, (4) standalone `gnomad://research-use` resource. gnomad-link currently implements levels 1, 2, and 3. Level 4 exists in pubtator-link as `get_research_use_resource()` returning a dedicated string resource but is not present in gnomad-link.

The `RESEARCH_USE_NOTICE = "Research use only; not for clinical decision support."` constant is correctly threaded through instructions, capabilities, and error envelopes.

### What Pushes Above 9.0

**Explicit `gnomad://research-use` resource.** A one-field resource `{"notice": RESEARCH_USE_NOTICE}` gives compliant clients a subscribable URI to inject into system prompts. This is a 5-line addition to `resources.py` and `tools/metadata.py`.

**`unsafe_for_clinical_use: true` on success responses, not just errors.** Currently `_meta.unsafe_for_clinical_use` only appears in error envelopes. It should appear on every tool response's `_meta` block. This is how a compliant client knows to attach a clinical-use warning before surfacing the data to a user, regardless of whether the call succeeded.

**Tool description safety language.** The spec section on security notes that tool descriptions from untrusted servers MUST be considered untrusted. For a trusted server, embedding safety language in the tool description is the right pattern: "...This data is for population genetics research; do not use to infer individual clinical risk." gnomad-link's instructions contain this language; it does not appear in individual tool descriptions. Either is acceptable; both is redundant.

### Anti-Patterns to Avoid

- Repeating the full safety notice in every tool description. It adds ~15 tokens per tool, 225 tokens total for 15 tools, at every `tools/list` call. The server instructions field is the right level of granularity for the safety notice.

### Trade-Offs

Adding `unsafe_for_clinical_use: true` to every success response adds ~35 bytes per call. Acceptable given the safety importance.

---

## Prioritised Action List

Ranked by (impact × ease), each labeled with which aspect(s) it lifts. Items 1-8 should be done before claiming >9.0 on all nine aspects.

| # | Action | Aspect(s) | Effort |
|---|---|---|---|
| 1 | **Upgrade `_meta.next_commands` to structured `{tool, arguments}` dicts in both error envelopes and success responses** — change `errors.py`'s static list to callable maps; add to `resolve_variant_id`, `get_gene_details`, `get_gene_variants`, `get_clinvar_variant_details` success paths | Composability, Error Surface | XS (30 lines) |
| 2 | **Add Pydantic validation error interception** — port pubtator-link's `install_validation_error_handler` pattern into `gnomad_link/mcp/facade.py`; intercepts `PydanticValidationError` and emits field-level `field_errors` array in the envelope | Error Surface | S (50 lines) |
| 3 | **Register 4 MCP prompts for core workflows** — `variant_frequency_workflow`, `gene_constraint_workflow`, `clinical_variant_workflow`, `region_scan_workflow` — each a short `@mcp.prompt` function returning a tool-sequence instruction string | Discoverability, Composability | S (40 lines + tests) |
| 4 | **Add property-level `examples` to discriminating input schema fields** — `variant_id` example `"1-55051215-G-GA"`, `gene_id` example `"ENSG00000169174"`, `populations` example `["afr","nfe"]`, `dataset` with all three values labelled by genome build | Schema Clarity | S (15 lines across 5 tool files) |
| 5 | **Add per-tool `summary` block to `get_variant_frequencies`** — top-level `summary: {overall_af, max_pop, max_pop_af, has_clinvar}` extracted from shaped populations; allows LLMs to answer AF questions without parsing the full populations array | Token Efficiency, Response Structure | S (20 lines in `shaping.py`) |
| 6 | **Extend `dataset` parameter descriptions to name genome builds explicitly** — `"gnomad_r4 (GRCh38, default, largest cohort), gnomad_r3 (GRCh38, whole-genome), gnomad_r2_1 (GRCh37 legacy)"` across tools that use the enum | Schema Clarity | XS (5 lines) |
| 7 | **Add `unsafe_for_clinical_use: true` to every tool success response's `_meta` block** — add to `run_mcp_tool` return-path in `errors.py` so it is emitted unconditionally | Research-Scope Clarity | XS (3 lines in `errors.py`) |
| 8 | **Add output schema validation interception** — port pubtator-link's `output_validation.py` `install_output_validation_error_handler`; converts FastMCP output-schema validation failures into actionable envelopes | Error Surface | S (60 lines + tests) |
| 9 | **Upgrade capabilities resource to include `llm_driver_contract` and `output_cheatsheet`** — add `recommended_entrypoint`, `core_workflow_tools` in order, and a field→JSON-path cheatsheet (`"frequency_populations": "exome.populations[]"`) | Discoverability, Response Structure | S (30 lines in `resources.py`) |
| 10 | **Add resource annotations to `gnomad://capabilities` and `gnomad://usage`** — `annotations={"audience": ["assistant"], "priority": 1.0}` — signals to compliant clients that these resources are high-priority AI context | Discoverability | XS (2 lines) |
| 11 | **Add `get_gnomad_diagnostics` tool** — closed-world, `readOnlyHint=True`, returns `get_recent_errors()` + server version + upstream health flag; gives error envelopes a concrete diagnostics entry point | Composability, Error Surface | M (80 lines + tests) |
| 12 | **Add `gnomad://research-use` resource** — single-field `{"notice": RESEARCH_USE_NOTICE}` as a subscribable URI for compliant clients to inject into system context | Research-Scope Clarity | XS (8 lines) |
| 13 | **Add tool `tags` for host-side filtering** — `tags={"variant"}`, `{"gene"}`, `{"clinical"}`, `{"coordinates"}`, `{"search"}`, `{"metadata"}` in each `@mcp.tool()` call | Speed, Discoverability | XS (15 lines) |
| 14 | **Add `tool_categories` and `tool_groups` to capabilities resource** — mirrors pubtator-link's `TOOL_CATEGORIES` dict; enables LLM to select the right category before loading individual tool schemas | Discoverability | S (20 lines in `resources.py`) |
| 15 | **Add `to_restore` alongside `to_disable` in truncated blocks** — clarifies the inverse operation when multiple filters are active simultaneously | Self-Documentation | XS (5 lines in `shaping.py`) |

**Effort key:** XS = <1 hour, S = 1-3 hours, M = 3-6 hours.

Items 1-8 together would lift the composite score to approximately 9.3/10 by the evaluation rubric. Items 9-15 push toward 9.5-9.7/10.

---

## Spec Gaps and Community Conventions

The following are **community patterns only** (not in the 2025-06-18 spec):

- `_meta.next_commands` field shape — no spec mandate; adopted by pubtator-link, sysndd, and several Anthropic examples
- `truncated.to_disable` pattern — no spec mandate; invented by this author
- `unsafe_for_clinical_use` in `_meta` — no spec mandate; domain convention
- `output_cheatsheet` in capabilities — no spec mandate; pubtator-link invention

The following **are** in the 2025-06-18 spec but not yet used by gnomad-link:

- `ToolDefinition.title` — human-readable display name separate from `name`; already used correctly via FastMCP's `title` parameter — DONE
- `Resource.annotations.audience` and `.priority` — not yet set on gnomad-link's resources
- `completions` capability for `prompts/get` argument autocomplete — not implemented; low priority for a 15-tool server
- Elicitation (`elicitation/create`) — server-initiated user-input requests; not appropriate for a read-only data server

---

## Sources

- MCP specification 2025-06-18: https://modelcontextprotocol.io/specification/2025-06-18
- MCP tools spec: https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- MCP resources spec: https://modelcontextprotocol.io/specification/2025-06-18/server/resources
- MCP prompts spec: https://modelcontextprotocol.io/specification/2025-06-18/server/prompts
- MCP elicitation spec: https://modelcontextprotocol.io/specification/2025-06-18/client/elicitation
- MCP completion spec: https://modelcontextprotocol.io/specification/2025-06-18/server/utilities/completion
- FastMCP tools docs: https://gofastmcp.com/servers/tools
- FastMCP prompts docs: https://gofastmcp.com/servers/prompts
- Anthropic engineering blog — writing tools for agents: https://www.anthropic.com/engineering/writing-tools-for-agents
- "MCP Tool Descriptions Are Smelly" (arxiv 2602.14878v1): https://arxiv.org/html/2602.14878v1
- BigData Boutique — 7 FastMCP mistakes: https://bigdataboutique.com/blog/building-mcp-servers-with-fastmcp-7-mistakes-to-avoid
- pubtator-link MCP reference codebase: `/home/bernt-popp/development/pubtator-link/pubtator_link/mcp/`
