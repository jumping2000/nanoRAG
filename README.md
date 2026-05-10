# nanoRAG

🚀 A modern, minimal, modular, production-ready Agentic RAG platform built with FastAPI, Agno, Next.js, Qdrant, and local hybrid retrieval.

## ✨ Overview

nanoRAG is designed for teams that want a clean RAG system without unnecessary infrastructure.

- 🧠 Agentic answer generation with Agno
- 🔎 Hybrid retrieval with dense search + BM25 + RRF
- 🗂️ Multi-knowledge-base support with KB-scoped chat and uploads
- 🧱 Single shared Qdrant collection filtered by `kb_id`
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
- Metadata catalog: local JSON records for knowledge bases and documents

### Retrieval flow

1. The user selects an active knowledge base.
2. The frontend sends the query with `kb_id`.
3. Dense retrieval searches Qdrant with a payload filter on `kb_id`.
4. Sparse retrieval searches the local BM25 index scoped to the same KB.
5. Results are fused with RRF.
6. The grounded context is sent to the knowledge agent.
7. The answer is streamed back to the UI.

## 🧩 Core capabilities

- Create, rename, and delete knowledge bases
- Upload documents into a specific knowledge base
- List and delete indexed documents per knowledge base
- Chat against one knowledge base at a time
- Surface source citations with chunk/document metadata
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

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- Qdrant: http://localhost:6333

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

## 📡 API overview

Main endpoints:

- `GET /health`
- `POST /kb`
- `GET /kb`
- `PATCH /kb/{kb_id}`
- `DELETE /kb/{kb_id}`
- `POST /kb/{kb_id}/upload`
- `GET /kb/{kb_id}/documents`
- `DELETE /kb/{kb_id}/documents/{document_id}`
- `POST /chat`

See the full API reference in [docs/api.md](docs/api.md).

## 🧪 Validation

Backend tests:

```bash
cd backend
uv run pytest
```

Frontend type check:

```bash
cd frontend
npm run typecheck
```

## 📚 Documentation

- [docs/architecture.md](docs/architecture.md)
- [docs/api.md](docs/api.md)
- [docs/backend.md](docs/backend.md)
- [docs/frontend.md](docs/frontend.md)
- [docs/hybrid-search.md](docs/hybrid-search.md)
- [docs/providers.md](docs/providers.md)

## 🎯 Design goals

- Minimal moving parts
- Clear boundaries between retrieval and reasoning
- Modular components without premature microservices
- Production-ready defaults with local-first ergonomics
- Easy extension path for future global or cross-KB retrieval

## 📄 License

Add the license that matches your intended GitHub distribution.