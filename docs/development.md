# Development

## Prerequisites

- Python 3.12+
- `uv`
- Node.js 22+
- Docker Desktop optional for full stack

## Backend setup

```bash
cd backend
uv sync
uv run uvicorn api.main:app --reload
```

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

## Useful commands

```bash
cd backend
uv run pytest
uv run ruff check .
uv run mypy .
uv run python graph_benchmark.py --fixture tests/fixtures/graph_benchmark_chunks.json
```

### Backend maintenance

Run these from `backend/` when you need to reconcile or wipe persistent state:

```bash
uv run python maintenance_cli.py delete-kb test
uv run python maintenance_cli.py rebuild-kb test2
uv run python maintenance_cli.py purge-qdrant-orphans
uv run python maintenance_cli.py reset-all
```

Recommended host override when the backend runs outside the container but Qdrant is exposed by Docker:

```bash
QDRANT_URL=http://localhost:6333 uv run python maintenance_cli.py purge-qdrant-orphans
QDRANT_URL=http://localhost:6333 uv run python maintenance_cli.py reset-all
```

Operational guidance:

- `delete-kb` is the safe path for removing one KB across all stores.
- `rebuild-kb` is recovery-only and works when sparse chunks still exist in `backend/data/chunks.jsonl`.
- `purge-qdrant-orphans` is useful after manual cleanup or old inconsistent states.
- `reset-all` is a cold reset and should usually be followed by a backend restart or container recreate.
- By default `reset-all` writes backup copies of the local metadata files before wiping them.

```bash
cd frontend
npm run typecheck
npm run build
```

## Debug notes

- BM25 state is rebuilt from `backend/data/chunks.jsonl` on startup.
- Qdrant stores the dense vectors and chunk payloads.
- The frontend expects the backend on `NEXT_PUBLIC_API_BASE_URL`.
- Structured graph extraction is disabled by default and can be enabled with `GRAPH_EXTRACTION_ENABLED=true`.
- The graph benchmark script is fixture-based and intended for local extractor comparisons before running manual smoke tests on real documents.
