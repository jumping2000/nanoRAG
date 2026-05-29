# Documentation Update: Query Expansion, Graph Retrieval & Observability

**Date:** 2026-05-29  
**Status:** approved → implementation  
**Depends on:** `2026-05-29-graph-query-expansion-retrieval-design.md` (implemented)

## Goal

Update existing documentation to reflect the implemented query expansion and graph retrieval features, and create a new observability document.

## Files Changed

### `README.md` — 5 changes

1. **Overview bullet**: add query expansion + graph retrieval mention
2. **Retrieval flow**: expand from 8 to 10 steps, adding optional query expansion (step 3) and optional graph retrieval (step 6), with RRF described as 2-way or 3-way
3. **Environment notes**: new section "Graph-augmented retrieval" listing the 4 env vars (`GRAPH_QUERY_EXPANSION_ENABLED`, `GRAPH_QUERY_EXPANSION_MAX_TERMS`, `GRAPH_RETRIEVAL_ENABLED`, `GRAPH_RETRIEVAL_TOP_K`)
4. **Roadmap**: mark Phase 1 and Phase 2 as `✅ done`
5. **Documentation list**: add `docs/observability.md`

### `docs/hybrid-search.md` — 5 changes

1. **New section**: "Query expansion from graph entities" — describes deterministic entity-label matching, tokenization, neighbor labels, cap at `GRAPH_QUERY_EXPANSION_MAX_TERMS`
2. **New section**: "Graph retrieval channel" — describes third channel, entity/relation scoring (0.35/0.65), confidence weighting, materialization via sparse chunk store, fallback entity lookup when expansion is off
3. **RRF fusion**: update formula description to mention 2-way vs 3-way
4. **Why this approach**: add bullets for optional query expansion and optional graph retrieval
5. **Graph-aware reranking scope**: remove "not query expansion" (no longer true)

### `docs/architecture.md` — 5 changes

1. **High-level components**: add 2 entries for query expansion and graph retrieval
2. **Retrieval flow Mermaid**: add `Query Expansion` and `Graph Retrieval` nodes, show 3-way RRF
3. **Chat flow sequence Mermaid**: add `Query Expander` and `Graph Retriever` participants
4. **Simplicity boundaries**: change "planned but not yet implemented" to "implemented and opt-in"
5. **Knowledge Graph → Retrieval integration**: expand from one paragraph to three bullets covering GraphReranker, GraphQueryExpander, and GraphRetriever

### `docs/observability.md` — new file

Covers:

- **APP_ENV modes**: production/development/debug comparison table
- **JSON structured logging**: format example, third-party logger silencing
- **Request correlation**: X-Request-ID via contextvars, middleware behavior
- **Trace collector**: debug-mode per-request event timeline, `/chat` NDJSON debug event
- **observe() function**: signature explanation
- **Event catalog**: tables for HTTP, API, Retrieval, Qdrant, Graph Store events
- **How to use**: local debugging and production examples
- **Current gaps**: metrics, distributed tracing, log shipping, sampling, LLM instrumentation, background tasks
- **Future directions**: 5-item roadmap

## Out of Scope

- `docs/backend.md` — already has "Graph-augmented retrieval" section (updated during implementation)
- `docs/api.md` — no endpoint changes
- `docs/mcp-server.md` — no MCP tool changes
- Frontend docs

## Verification

- Manual review of each file for consistency with code
- Check no stale "planned" references remain
- Verify observability event catalog matches actual `observe()` calls in source
