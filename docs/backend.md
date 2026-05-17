# Backend

The backend is a single FastAPI service organized around retrieval, ingestion and agent execution.

## Structure

- `api/`: FastAPI application and endpoints.
- `agents/`: Orchestrator and Knowledge agent wrappers built with Agno.
- `chunking/`: structural chunking logic.
- `providers/`: LLM and embedding provider abstraction.
- `retrieval/`: dense search, sparse BM25 and fusion.
- `rag/`: ingestion, KB/document catalog, and metadata helpers.
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
4. Feed top chunks to the Knowledge Agent.

## Ingestion policy

Uploads are parsed in-memory.

- PDFs are read with `pypdf`
- TXT and Markdown are decoded directly
- only chunks and metadata are persisted
- raw source files are discarded after extraction

## API runtime

The application keeps a shared in-process retriever stack:

- `EmbeddingProvider`
- `DenseRetriever`
- `SparseRetriever`
- `HybridRetriever`
- `MetadataCatalog`
- `IngestionService`

This keeps the service simple and avoids premature orchestration layers.

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
