# Docker

The repository ships with a single `docker-compose.yml` for local deployment.

## Services

- `frontend`: Next.js production server
- `backend`: FastAPI application with uv
- `qdrant`: vector database
- `ollama`: optional local LLM service via Compose profile

## Start the stack

```bash
docker compose up --build
```

Enable Ollama only when needed:

```bash
docker compose --profile local-llm up --build
```

## Healthchecks

- Qdrant: `GET /readyz`
- Backend: `GET /health`
- Frontend: root page HTTP check
- Ollama: `ollama list`

## Volumes

- `qdrant_data`: persistent vector storage
- `ollama_data`: local Ollama models
- `./backend/data`: uploaded files and chunk store
