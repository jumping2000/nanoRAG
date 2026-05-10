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
```

```bash
cd frontend
npm run typecheck
npm run build
```

## Debug notes

- BM25 state is rebuilt from `backend/data/chunks.jsonl` on startup.
- Qdrant stores the dense vectors and chunk payloads.
- The frontend expects the backend on `NEXT_PUBLIC_API_BASE_URL`.
