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
