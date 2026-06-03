# nanoRAG — Docker

The repository ships with a single `docker-compose.yml` for local deployment.

## Services

- `nginx`: reverse proxy (public entrypoint, port 8000)
- `frontend`: Next.js production server (internal)
- `backend`: FastAPI application with uv (internal)
- `mcp`: dedicated MCP HTTP service (internal)
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

## nginx front door

Create the Basic Auth file before starting Compose:

```bash
docker run --rm httpd:2.4-alpine htpasswd -nbB admin changeme > nginx/.htpasswd
```

Required environment variables:

- `MCP_API_KEY` — secret used by nginx for `/mcp`
- `MCP_HTTP_PORT` — internal listen port for the `mcp` service
- `MCP_HTTP_URL` — optional upstream override, defaults to `http://mcp:${MCP_HTTP_PORT}/mcp`

Public authentication model:

- `Basic Auth` for UI and backend API
- `X-API-Key` only for `/mcp`
