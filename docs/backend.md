# Backend

The backend is a single FastAPI service organized around retrieval, ingestion and agent execution.

## Structure

- `api/`: FastAPI application and endpoints.
- `agents/`: Orchestrator and Knowledge agent wrappers built with Agno.
- `chunking/`: structural chunking logic.
- `providers/`: LLM and embedding provider abstraction.
- `retrieval/`: dense search, sparse BM25 and fusion.
- `rag/`: ingestion and metadata helpers.
- `db/`: Qdrant client bootstrap.

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

1. Embed query for dense search.
2. Run BM25 locally on indexed chunks.
3. Merge rankings with RRF.
4. Feed top chunks to the Knowledge Agent.

## API runtime

The application keeps a shared in-process retriever stack:

- `EmbeddingProvider`
- `DenseRetriever`
- `SparseRetriever`
- `HybridRetriever`
- `IngestionService`

This keeps the service simple and avoids premature orchestration layers.
