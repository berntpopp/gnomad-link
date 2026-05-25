# gnomAD Link MCP Facade Migration Design

## Context

`gnomad-link` currently exposes MCP tools through `FastMCP.from_fastapi()` in
`gnomad_link/server_manager.py`. This keeps REST and MCP cheap to maintain, but
it makes the FastAPI/OpenAPI route surface the LLM-facing contract. The recent
MCP review found concrete drift caused by that coupling:

- OpenAPI examples for search and variant frequency endpoints advertise fields
  that the runtime response models or GraphQL selections do not return.
- MCP tools inherit REST summaries instead of LLM-routing descriptions.
- MCP has no server `instructions`, capabilities resource, or tool annotations.
- The `mcp_custom_names` mapping contains stale operation IDs that do not map to
  active routes.
- High-token responses expose REST-style full resources by default instead of
  compact, projection-oriented MCP outputs.

The sibling `pubtator-link` repository still keeps a FastAPI REST/OpenAPI app,
but its active MCP server is hand-authored in `pubtator_link/mcp/facade.py` and
mounted into the same HTTP process. That is the target shape for `gnomad-link`.

## Goal

Make MCP a first-class, hand-authored facade over the gnomAD service layer while
preserving the existing REST API and Docker/HTTP deployment shape.

## Non-Goals

- The REST surface is intentionally reduced to `/health` only.
- `/docs`, `/redoc`, `/openapi.json`, and all `/variant` `/gene` `/clinvar`
  etc. routes are removed.
- `/cache/stats` and `/cache/clear` move to the CLI.
- `search_variants` becomes a deprecated alias for `resolve_variant_id`;
  one-release removal window.
- Do not import PubTator's review/RAG profile complexity.
- Do not expose destructive cache operations through MCP.
- Do not broaden default local CI to live gnomAD API calls.

## Architecture

The source of truth is the service/client layer:

```text
FastAPI /health host
        |
        +-- /mcp -> FastMCP HTTP app
                         |
gnomad_link.mcp.*         -> hand-authored MCP facade
                         /
gnomad_link.services.*    -> shared service and GraphQL client layer
```

`UnifiedServerManager.create_mcp_server()` should call
`gnomad_link.mcp.facade.create_gnomad_mcp(service_factory=service_factory)` instead of
`FastMCP.from_fastapi()` with the FastAPI app as its source. The
`service_factory` is a lazy callable returning the active `FrequencyService`.
In unified HTTP mode it reads `app.state.frequency_service`, so REST and MCP use
one service instance, cache, and client. In stdio mode the manager constructs
one `FrequencyService` directly and passes a closure returning it. The HTTP
mount and lifespan behavior added for modern Streamable HTTP should remain:
create `mcp.http_app(path="/")`, compose lifespans, and mount at
`config.mcp_path`.

The initial facade should preserve the current public MCP tool names:

- `get_variant_frequencies`
- `get_variant_details`
- `get_gene_details`
- `get_gene_variants`
- `get_clinvar_variant_details`
- `get_clinvar_meta`
- `liftover_variant`
- `get_structural_variant`
- `get_mitochondrial_variant`
- `get_region`
- `get_transcript_details`
- `search_genes`
- `search_variants`

Add one new MCP-only discoverability tool. It remains unprefixed to match the
existing public gnomAD tool naming convention:

- `get_server_capabilities`

`get_clinvar_meta` stays as a parity tool even though its payload is small. It
is useful for clients that need the ClinVar release date without fetching the
larger capabilities resource.

## MCP Contract

Every MCP tool should be explicitly registered with:

- LLM-oriented description text beginning with "Use this when..."
- concrete input constraints using `typing.Annotated` and `pydantic.Field`
- output schema where the response shape is stable
- `ToolAnnotations(readOnlyHint=True, destructiveHint=False,
  idempotentHint=True, openWorldHint=True)` for gnomAD API-backed tools
- `openWorldHint=False` for local capabilities/usage metadata

Server instructions should be short enough for every session start and include:

- canonical workflows for variant frequency, clinical annotation pairing,
  gene constraint, coordinate conversion, region lookup, and search fallback
- dataset/build mapping: `gnomad_r2_1` on GRCh37, `gnomad_r3` and `gnomad_r4`
  on GRCh38
- mitochondrial and structural variant routing hints
- research-use-only language
- pointer to `get_server_capabilities` and `gnomad://capabilities`

Resources:

- `gnomad://capabilities` returns supported tools, datasets, reference builds,
  population codes, known limitations, and recommended workflows.
- `gnomad://usage` returns compact Markdown usage guidance for clients that can
  read MCP resources.

## Response Strategy

Phase 1 should preserve current tool behavior as much as possible while moving
ownership to the MCP facade. It may adapt envelopes only where the current MCP
surface is already a FastMCP artifact, such as list returns wrapped as
an object containing a `result` array.

Phase 2 should add compact MCP-native response shaping:

- `get_variant_frequencies` adds `populations`, `include_subcohorts`,
  `include_sex_split`, and `exclude_zero_populations` parameters. Defaults
  should minimize tokens while still returning useful total exome/genome counts.
  The exact subcohort filtering rule must be based on a live population-ID spike
  before tests codify any `1kg:*` or other dataset-specific assumptions.
- Frequency-bearing rows include serialized `af` computed from `ac/an` when the
  upstream value is missing.
- `get_variant_details` adds `response_mode: "compact" | "full" = "compact"`.
- `get_gene_variants` adds `limit`, `consequence`, `max_af`, and `min_ac`.
- Large responses include explicit truncation metadata when results are
  filtered or limited.

`search_variants` remains ID-only in the parity phase because the current
GraphQL document selects only `variant_id`. Its MCP description and capability
guidance must say this directly and route callers to `get_variant_frequencies`
or `get_variant_details`. Enriching search results is a separate follow-up after
verifying which fields gnomAD search can return without N extra detail calls.

REST/OpenAPI example cleanup remains valuable, but it is a separate follow-up:
REST docs should stop lying, but MCP should no longer depend on REST examples.

## Testing

Add MCP-specific unit tests that instantiate `create_gnomad_mcp()` with a stub
`service_factory` and verify:

- expected public tool names are present
- no stale FastAPI operation IDs are referenced
- all tool names match the Anthropic remote MCP regex
- `instructions` contains the canonical workflow and research-use language
- capabilities tool and resources exist and `gnomad://capabilities` is readable
- every gnomAD data tool has read-only/idempotent/open-world annotations
- compact-mode defaults and frequency filtering parameters appear in schemas

Add focused adapter tests for new response-shaping helpers using stubbed service
responses. Keep live gnomAD validation in `tests/integration/`.

## Risks

- A hand-authored facade duplicates some parameter declarations. Tests must lock
  tool names and schemas to prevent drift.
- Changing MCP envelopes may affect existing MCP clients. Preserve current tool
  names and make shape changes intentional in the plan.
- `exclude_zero_populations=True` is a token-saving MCP behavior change. It must
  be documented in capabilities and can be disabled by callers.
- Some GraphQL search endpoints only return IDs today. Enrichment may require
  extra GraphQL selections or follow-up detail calls; implementation must verify
  what gnomAD actually supports before promising fields.
- Tool annotations are advisory hints, not security boundaries. Cache-clearing
  and other destructive operations must remain unregistered in MCP.
