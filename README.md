# nanoRAG

🚀 A modern, minimal, modular Agentic Hybrid RAG platform with knowledge graph exploration — built with FastAPI, Agno, Next.js, Qdrant, and local hybrid retrieval.

## ✨ Overview

nanoRAG is designed for teams that want a clean RAG system without unnecessary infrastructure.

- 🧠 Agentic answer generation with Agno
- 🔎 Hybrid retrieval with dense search + BM25 + graph retrieval + RRF
- 🧩 Query expansion from knowledge graph entities (deterministic, no LLM)
- 🔁 Graph-aware reranking on the `/chat` path
- 🕸️ Knowledge graph extraction with structured LLM pipeline and KB-scoped inspection
- 🗺️ Graph node detail API with evidence-backed relation inspection
- 🗂️ Multi-knowledge-base support with KB-scoped chat and uploads
- 🧱 Single shared Qdrant collection filtered by `kb_id`
- 🔌 MCP server for agentic access (stdio + streamable-http)
- 💻 CPU-friendly backend, including CPU-only PyTorch setup
- 🌊 Streaming chat responses over NDJSON
- 🛡️ No raw PDF/TXT/MD retention after ingestion, only chunks and metadata

## 🏗️ Architecture

The platform keeps retrieval and reasoning strictly separated.

- Frontend: Next.js App Router + React 19
- Backend: FastAPI + Agno
- Vector store: Qdrant
- Sparse retrieval: `rank-bm25`
- Fusion: Reciprocal Rank Fusion
- Graph store: SQLite-backed mention-level knowledge graph
- Graph reranker: configurable entity/relation weighting on chat candidates
- Metadata catalog: local JSON records for knowledge bases and documents

### Retrieval flow

1. The user selects an active knowledge base.
2. The frontend sends the query with `kb_id`.
3. (Optional) Query expansion enriches the query with matched entity labels from the knowledge graph.
4. Dense retrieval searches Qdrant with a payload filter on `kb_id`.
5. Sparse retrieval searches the local BM25 index scoped to the same KB.
6. (Optional) Graph retrieval pulls chunk candidates directly from graph mention evidence.
7. All channels are fused with RRF (2-way or 3-way depending on active channels).
8. The fused chunks are reranked with a graph-aware pass using entity and relation evidence from SQLite (configurable weights).
9. The grounded context is sent to the knowledge agent.
10. The answer is streamed back to the UI.

## 🧩 Core capabilities

- Create, rename, and delete knowledge bases
- Upload documents into a specific knowledge base
- List and delete indexed documents per knowledge base
- Chat against one knowledge base at a time
- Surface source citations with chunk/document metadata
- Build a KB-scoped knowledge graph from chunk text and inspect node-level evidence
- Gently promote relation-bearing chunks during chat without replacing the existing hybrid retriever
- Keep infrastructure simple enough for local development and small production deployments

## 📁 Project structure

```text
backend/     FastAPI app, ingestion, retrieval, agent orchestration, tests
frontend/    Next.js UI, KB workspace shell, streaming chat client
docs/        API, architecture, backend, frontend, retrieval notes
```

## ⚙️ Requirements

- Python 3.12+
- Node.js 20+
- `uv`
- Docker and Docker Compose (optional, recommended for full local stack)

## 🚀 Quick start

### 1. Clone and configure

```bash
git clone <your-repo-url>
cd nanoRAG
cp .env.example .env
```

Fill in the provider settings you want to use in `.env`.

### 2. Run with Docker

```bash
docker compose -f docker-compose.yml up --build
```

Services:

- Public entrypoint: http://localhost:8000
- Qdrant: http://localhost:6333

Public access rules:

- UI and backend HTTP API require Basic Auth through nginx
- `/mcp` requires `X-API-Key` and does not use Basic Auth
- backend, frontend, and mcp are internal-only in Compose

## 🛠️ Local development

### Backend

```bash
cd backend
uv sync --dev
uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## 🔌 Environment notes

The backend supports multiple providers for both LLMs and embeddings.

- `openai`
- `openrouter`
- `ollama`

Important runtime details:

- PyTorch is pinned to the CPU wheel index
- Retrieval is local and CPU-friendly
- Uploaded source files are processed in-memory and discarded after ingestion

### Knowledge graph extraction

The graph pipeline now has two modes:

- default heuristic extraction through `backend/rag/graph_extractor.py`
- optional structured extraction through `backend/rag/structured_graph_extractor.py`

Structured extraction is disabled by default and can be rolled out behind these flags:

- `GRAPH_EXTRACTION_ENABLED`
- `GRAPH_EXTRACTION_PROVIDER`
- `GRAPH_EXTRACTION_MODEL`
- `GRAPH_EXTRACTION_MAX_CHUNKS_PER_DOCUMENT`
- `GRAPH_EXTRACTION_MIN_CONFIDENCE`

Important behavior:

- ingestion never fails only because graph extraction failed for one chunk
- when structured extraction is enabled, the backend caps graph extraction work per document with `GRAPH_EXTRACTION_MAX_CHUNKS_PER_DOCUMENT`
- the runtime keeps the heuristic extractor as fallback if structured extraction returns invalid output
- upload completion no longer waits for structured graph extraction; document catalog writes complete first and graph work continues in the background

### Graph-aware reranking

The chat path now adds one minimal graph-aware reranking step after dense + BM25 + RRF.

Current behavior:

- the base retriever still decides the candidate set
- the backend loads chunk-scoped graph evidence from `backend/data/knowledge_graph.db`
- chunks with stronger relation evidence receive a conservative bonus
- retrieval remains the dominant signal, so weak or missing graph evidence preserves the original order

Current scope:

- active only on `POST /chat`
- uses graph evidence already persisted during ingestion
- does not replace RRF or multi-hop traversal
- does not change the graph inspection APIs

### Graph-augmented retrieval (query expansion & graph retrieval)

Two opt-in retrieval features, independent and additive to the existing hybrid retriever:

- `GRAPH_QUERY_EXPANSION_ENABLED` (default: `false`) — enrich queries with matched entity labels before retrieval
- `GRAPH_QUERY_EXPANSION_MAX_TERMS` (default: `4`) — max added terms per query
- `GRAPH_RETRIEVAL_ENABLED` (default: `false`) — add a third retrieval channel from graph mention evidence
- `GRAPH_RETRIEVAL_TOP_K` (default: `6`) — max candidates from the graph channel

Both default to `false`; the chat path behaves identically to previous versions when disabled.

### `APP_ENV` modes

The backend now exposes three observability profiles through `APP_ENV`:

- `production`: light logs, warnings and errors only
- `development`: deeper request and application logs for normal local debugging
- `debug`: detailed request tracing with backend and database operation metadata

When `APP_ENV` is `development` or `debug`, API responses include `X-Request-ID` and `X-Debug-Trace-Mode` headers.

When `APP_ENV` is `debug`, the backend also emits technical trace events for request handling, retrieval, embeddings, Qdrant and SQLite operations. The `/chat` NDJSON stream includes an extra final `debug` event with the trace snapshot.

## 📡 API overview

Main endpoints:

- `GET /health`
- `POST /kb`
- `GET /kb`
- `PATCH /kb/{kb_id}`
- `DELETE /kb/{kb_id}`
- `POST /kb/{kb_id}/upload`
- `GET /kb/{kb_id}/documents`
- `GET /kb/{kb_id}/graph`
- `GET /kb/{kb_id}/graph/node/{entity_id}`
- `DELETE /kb/{kb_id}/documents/{document_id}`
- `POST /chat`

See the full API reference in [docs/api.md](docs/api.md).

### MCP server

nanoRAG exposes a **Model Context Protocol** surface for agentic access. The MCP server supports two transports:

- `stdio` (default): runs as a subprocess inside the backend, communicating over NDJSON-framed JSON-RPC
- `streamable-http`: runs as a standalone HTTP server (default port `8100`, configurable via `MCP_HTTP_PORT`)

The public MCP endpoint is exposed by nginx at `/mcp` and forwarded to a dedicated MCP service running in `streamable-http` mode. The backend no longer proxies MCP traffic over HTTP. Local standalone MCP clients should use the `stdio` transport by launching `python mcp_server_start.py` directly, while the frontend uses the same public origin behind nginx.

- 8 MCP tools for KB inspection, chat, graph exploration, and document management
- Same runtime as the REST API — shared retrieval, graph store, and agents

Connect Claude Desktop or VS Code Copilot (point at the nginx MCP endpoint):

```json
{
  "mcpServers": {
    "nanoRAG": {
      "transport": "streamable-http",
      "url": "http://localhost:8000/mcp",
      "env": {
        "MCP_API_KEY": "YKmq57LwGDoNY2hj"
      }
    }
  }
}

See the full MCP reference in [docs/mcp-server.md](docs/mcp-server.md).

## 🧪 Validation

Backend tests:

```bash
cd backend
uv run pytest
```

Graph extractor benchmark fixture:

```bash
cd backend
uv run python graph_benchmark.py --fixture tests/fixtures/graph_benchmark_chunks.json
```

Reranking behavior is covered by backend tests as part of the normal suite, including a chat-path assertion that the reranked chunk order reaches both the knowledge agent and emitted sources.

Frontend type check:

```bash
cd frontend
npm run typecheck
```

## 🧰 Maintenance

The backend now includes two maintenance surfaces:

- `backend/maintenance.py`: Python service functions for cross-store cleanup and recovery.
- `backend/maintenance_cli.py`: command-line wrapper around those functions.

What they do:

- `delete-kb <kb_id>`: removes one KB from metadata JSON, sparse chunk store, graph SQLite, and Qdrant.
- `rebuild-kb <kb_id>`: reconstructs KB metadata and document records from `backend/data/chunks.jsonl` when sparse chunks still exist but the catalog was lost.
- `purge-qdrant-orphans`: removes Qdrant points with missing `kb_id` payloads.
- `reset-all`: wipes metadata JSON, sparse chunks, graph DB, uploads, and the configured Qdrant collection.

Run from `backend/`:

```bash
cd backend
uv run python maintenance_cli.py delete-kb test
uv run python maintenance_cli.py rebuild-kb test2
uv run python maintenance_cli.py purge-qdrant-orphans
uv run python maintenance_cli.py reset-all
```

Notes:

- `reset-all` creates backup copies of `knowledge_bases.json`, `documents.json`, and `chunks.jsonl` by default.
- Use `--no-backup` only when you explicitly want a destructive reset with no local metadata backup.
- When running the CLI from the host instead of inside Docker, ensure `QDRANT_URL` points to the host-exposed service, typically `http://localhost:6333`.

## 📚 Documentation

- [docs/architecture.md](docs/architecture.md)
- [docs/api.md](docs/api.md)
- [docs/backend.md](docs/backend.md)
- [docs/development.md](docs/development.md)
- [docs/docker.md](docs/docker.md)
- [docs/frontend.md](docs/frontend.md)
- [docs/hybrid-search.md](docs/hybrid-search.md)
- [docs/providers.md](docs/providers.md)
- [docs/mcp-server.md](docs/mcp-server.md)
- [docs/observability.md](docs/observability.md)
- [docs/tests.md](docs/tests.md)

## 🎯 Design goals

- Minimal moving parts
- Clear boundaries between retrieval and reasoning
- Modular components without premature microservices
- Production-ready defaults with local-first ergonomics
- Easy extension path for future global or cross-KB retrieval
- Graph extraction is additive to retrieval, not a replacement

## 🗺️ Roadmap

The knowledge graph currently powers inspection and conservative reranking.
Planned retrieval-path integrations:

| Phase | Feature | Status |
|-------|---------|--------|
| 1 | Query expansion from graph entities | ✅ done |
| 2 | Graph retrieval as third retrieval channel | ✅ done |
| 3 | Multi-hop traversal for relational queries | _planned_ |

## 📄 License

MIT License