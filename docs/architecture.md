# Architecture

nanoRAG is a minimal agentic RAG platform with a strict separation between retrieval and reasoning.

## Principles

- Retrieval is isolated from agents.
- Orchestration is intentionally small.
- Hybrid search is local and CPU-friendly.
- The backend stays monolithic and modular.
- The frontend is client-heavy, responsive and streaming-first.

## High-level components

- Frontend: Next.js App Router, React 19, TailwindCSS, shadcn-style primitives.
- Backend: FastAPI + Agno for agent execution.
- Vector search: Qdrant.
- Sparse retrieval: local BM25 with rank-bm25.
- Fusion: Reciprocal Rank Fusion.
- Providers: OpenAI-compatible APIs and Ollama.

## Retrieval flow

```mermaid
flowchart TD
    A[User Query] --> B[Orchestrator Agent]
    B --> C[Hybrid Retriever]
    C --> D[Dense Search in Qdrant]
    C --> E[BM25 Sparse Search]
    D --> F[RRF Fusion]
    E --> F
    F --> G[Top Chunks]
    G --> H[Knowledge Agent]
    H --> I[Streaming Markdown Response]
```

## Chat flow

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Next.js Frontend
    participant API as FastAPI
    participant OR as Orchestrator Agent
    participant HR as Hybrid Retriever
    participant KA as Knowledge Agent

    U->>FE: Send message
    FE->>API: POST /chat
    API->>OR: Generate retrieval plan
    API->>HR: dense + sparse retrieval
    HR-->>API: fused chunks
    API->>KA: grounded prompt with chunks
    KA-->>API: streaming tokens
    API-->>FE: NDJSON token stream
    FE-->>U: live rendered answer + citations
```

## Simplicity boundaries

This version deliberately excludes:

- semantic chunking with LLMs
- reranking
- planner agents
- distributed memory
- background job systems
- microservices
