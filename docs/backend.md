# Backend

The backend is a single FastAPI service organized around retrieval, ingestion and agent execution.

## Structure

- `api/`: FastAPI application and endpoints.
- `agents/`: Orchestrator and Knowledge agent wrappers built with Agno.
- `chunking/`: structural chunking logic.
- `providers/`: LLM and embedding provider abstraction.
- `retrieval/`: dense search, sparse BM25, fusion, and graph-aware reranking.
- `rag/`: ingestion, KB/document catalog, graph extraction/store, and metadata helpers.
- `db/`: Qdrant client bootstrap.

## Multi-KB design

- one shared Qdrant collection: `nanorag_chunks`
- chunk payload isolation via `kb_id`
- local metadata catalog for KB and document records only
- no persisted raw uploads after processing

## Agents

### Orchestrator Agent

Responsibilities:

- normalize the incoming question
- preserve acronyms and exact technical terms
- produce a minimal retrieval plan
- fall back deterministically if the model output is not parseable

The orchestrator does not retrieve data directly.

### Knowledge Agent

Responsibilities:

- answer using only retrieved chunks
- emit grounded Markdown
- cite sources as `[S1]`, `[S2]`, ...
- state when context is insufficient

## Retrieval pipeline

1. Require an active `kb_id`.
2. Embed query for dense search.
3. Query Qdrant with a payload filter on `kb_id`.
4. Run BM25 locally on the in-memory chunk corpus for that `kb_id`.
5. Merge rankings with RRF.
6. Apply a conservative graph-aware reranking pass using graph evidence already stored per chunk.
7. Feed top chunks to the Knowledge Agent.

### Graph-aware reranking

The first graph-aware improvement is intentionally narrow.

Current runtime behavior:

- reranking runs only on `POST /chat`
- the candidate set still comes from dense + sparse + RRF
- the backend reads chunk-scoped graph evidence from the SQLite graph store
- relation-bearing chunks receive more bonus than entity-only chunks
- if graph evidence is absent or weak, the original hybrid order is preserved

The implementation is split across:

- `backend/retrieval/graph_reranker.py`: conservative post-retrieval reranking logic
- `backend/rag/graph_store.py`: chunk-batch graph summary lookup for reranking
- `backend/api/main.py`: chat-path wiring

This keeps graph-aware behavior additive rather than invasive.

## Ingestion policy

Uploads are parsed in-memory.

- PDFs are read with `pypdf`
- TXT and Markdown are decoded directly
- only chunks and metadata are persisted
- raw source files are discarded after extraction

## Knowledge graph pipeline

The backend builds a KB-scoped knowledge graph from chunk text during ingestion.

Current runtime behavior:

- chunk text is analyzed immediately after dense and sparse indexing
- graph facts are stored in SQLite as mention-level rows
- graph extraction errors are isolated at chunk level and do not fail the whole upload
- document catalog writes complete before optional structured graph extraction finishes, so uploads do not stay blocked waiting for graph work

### Extraction modes

Two extractor paths now exist:

- heuristic extractor: `backend/rag/graph_extractor.py`
- structured extractor: `backend/rag/structured_graph_extractor.py`

The structured extractor is behind feature flags in `Settings`:

- `GRAPH_EXTRACTION_ENABLED`
- `GRAPH_EXTRACTION_PROVIDER`
- `GRAPH_EXTRACTION_MODEL`
- `GRAPH_EXTRACTION_MAX_CHUNKS_PER_DOCUMENT`
- `GRAPH_EXTRACTION_MIN_CONFIDENCE`

Default behavior:

- `GRAPH_EXTRACTION_ENABLED=false`: the backend uses the heuristic extractor only
- `GRAPH_EXTRACTION_ENABLED=true`: the backend tries structured extraction and falls back to the heuristic extractor if the structured output is invalid at runtime

The structured extractor uses:

- `backend/prompts/graph_extraction.md` for the extraction instructions
- `backend/rag/graph_normalization.py` for deterministic entity and predicate normalization
- `backend/models.py` extraction DTOs as the trusted schema boundary for model output

### Graph read surfaces

The backend now exposes two graph read paths:

- snapshot overview: `GET /kb/{kb_id}/graph`
- node inspection: `GET /kb/{kb_id}/graph/node/{entity_id}`

The snapshot endpoint is intentionally small and overview-first.
The node-detail endpoint lazily loads richer evidence, grouped relations, and backing documents for one entity.

### Benchmark harness

The repository now includes a fixture-based extractor comparison harness in `backend/graph_benchmark.py`.

Run from `backend/`:

```bash
uv run python graph_benchmark.py --fixture tests/fixtures/graph_benchmark_chunks.json
```

What it reports:

- entity and relation mention counts per extractor
- unique entities and unique relations
- predicate distribution
- chunk-level deltas between heuristic and structured extraction
- chunk failures in the candidate extractor

## API runtime

The application keeps a shared in-process retriever stack:

- `EmbeddingProvider`
- `DenseRetriever`
- `SparseRetriever`
- `HybridRetriever`
- `GraphReranker`
- `MetadataCatalog`
- `IngestionService`

This keeps the service simple and avoids premature orchestration layers.

The graph runtime is built into the same shared process stack through `build_ingestion_runtime()`.
This is where the extractor implementation is selected and the fallback behavior is wired.
The reranker reuses the same in-process graph store and does not introduce a second retrieval service.

## Maintenance utilities

The backend also exposes a maintenance layer outside the FastAPI endpoints.

- [backend/maintenance.py](c:/Users/gpamm/Documents/develop/nanoRAG/backend/maintenance.py): reusable service functions for destructive cleanup and partial recovery.
- [backend/maintenance_cli.py](c:/Users/gpamm/Documents/develop/nanoRAG/backend/maintenance_cli.py): thin CLI wrapper over the maintenance service.

### `maintenance.py`

The module provides four operational functions:

- `delete_kb_totally(settings, kb_id)`: performs a full KB delete across all stores by reusing the ingestion deletion path.
- `rebuild_kb_from_sparse_chunks(settings, kb_id)`: rebuilds catalog metadata for a KB from sparse chunks already present in `chunks.jsonl`.
- `purge_orphan_qdrant_points(settings)`: scans Qdrant and deletes points whose payload has no `kb_id`.
- `reset_all_state(settings)`: resets local JSON metadata, sparse chunks, graph DB, uploads, and deletes the configured Qdrant collection.

Store coverage by operation:

- Metadata catalog: `knowledge_bases.json`, `documents.json`
- Sparse retrieval: `chunks.jsonl`
- Graph store: `knowledge_graph.db`
- Upload staging: `backend/data/uploads`
- Dense retrieval: Qdrant collection from `QDRANT_COLLECTION`

Important behavior:

- `rebuild_kb_from_sparse_chunks` can restore catalog visibility only if sparse chunks still exist locally.
- It does not recreate original PDF files and cannot recover missing dense vectors if both sparse chunks and Qdrant data are gone.
- `reset_all_state` is intentionally destructive and should be treated like a cold reset of backend persistence.

### `maintenance_cli.py`

The CLI is intended for local maintenance and recovery tasks.

Run from `backend/`:

```bash
uv run python maintenance_cli.py delete-kb <kb_id>
uv run python maintenance_cli.py rebuild-kb <kb_id>
uv run python maintenance_cli.py purge-qdrant-orphans
uv run python maintenance_cli.py reset-all
```

Additional options:

- `uv run python maintenance_cli.py reset-all --no-backup`

Output:

- All commands print JSON to stdout.
- `reset-all` returns the number of deleted upload entries, whether the Qdrant collection was deleted, and the backup files created.
- `delete-kb` returns the same store-by-store deletion summary used by the backend service layer.

Environment notes:

- The CLI resolves configuration through `get_settings()` exactly like the application.
- If you run it on the host while Docker is exposing Qdrant on port `6333`, set `QDRANT_URL=http://localhost:6333` when needed.
- If you run it inside the backend container, the container env is already aligned with `http://qdrant:6333`.

## Observability modes

`APP_ENV` now drives three backend observability levels:

- `production`: only light operational logging, warnings and errors
- `development`: request lifecycle, retrieval flow, ingestion flow and agent fallback visibility
- `debug`: adds per-request trace collection plus technical database metadata for Qdrant and SQLite operations

The backend assigns a request correlation ID to every HTTP request and returns it as `X-Request-ID`.

Additional response behavior:

- `development`: adds `X-Debug-Trace-Mode: development`
- `debug`: adds `X-Debug-Trace-Mode: debug` and `X-Debug-Trace-Events`

The `debug` profile intentionally logs only technical metadata such as status, timings, counts, filters, hit counts and row counts. It does not log full prompts or full document payloads.

For `POST /chat`, the NDJSON response appends a `debug` event before `done`, containing the request trace snapshot.
