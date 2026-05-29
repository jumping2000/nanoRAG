# nanoRAG — Observability

nanoRAG uses structured JSON logging, per-request trace collection, and
environment-gated debug profiles. All observability is local and in-process —
no external collectors required.

## APP_ENV modes

The `APP_ENV` variable controls log verbosity and trace detail:

| Mode | Log level | X-Request-ID | Trace events | Debug trace in /chat |
|------|-----------|-------------|-------------|---------------------|
| `production` | WARNING | No | No | No |
| `development` | INFO | Yes | No | No |
| `debug` | DEBUG | Yes | Yes | Yes |

Set via `.env`:
```bash
APP_ENV=debug
```

## JSON structured logging

All backend logs are emitted as single-line JSON objects. The formatter
(`backend/observability.py:JsonLogFormatter`) produces:

```json
{
  "timestamp": "2026-05-29T14:22:00.123Z",
  "level": "INFO",
  "logger": "api.main",
  "message": "http.request.completed",
  "request_id": "a1b2c3d4",
  "environment": "development",
  "event": "http.request.completed",
  "details": {
    "method": "POST",
    "path": "/chat",
    "status_code": 200,
    "elapsed_ms": 342.5
  }
}
```

Third-party loggers (`httpx`, `openai`) are silenced to WARNING to reduce noise.

## Request correlation

Every HTTP request gets a unique `X-Request-ID` (UUID hex, or inherited from
the `X-Request-ID` header if the caller provides one). This ID propagates
through all log entries and trace events for that request via Python
`contextvars`.

Middleware (`api/main.py:observability_middleware`):
- Generates or inherits `request_id`
- Sets `environment` from `APP_ENV`
- Records `http.request.started` and `http.request.completed` events
- Attaches `X-Request-ID` and `X-Debug-Trace-Mode` to responses (dev/debug only)
- Attaches `X-Debug-Trace-Events` with event count (debug only)

## Trace collector (debug mode)

When `APP_ENV=debug`, a `TraceCollector` accumulates a per-request event
timeline. Each `observe()` call writes to both the JSON log and the trace
collector.

The trace snapshot is emitted as a `debug` event at the end of `/chat`
NDJSON streams:

```json
{"type": "debug", "trace": {
  "requestId": "a1b2c3d4",
  "environment": "debug",
  "elapsedMs": 342.5,
  "events": [
    {"at": "...", "component": "http", "action": "request.started", "details": {...}},
    {"at": "...", "component": "retrieval", "action": "query_expansion.completed", "details": {...}},
    {"at": "...", "component": "qdrant", "action": "search.completed", "details": {...}}
  ]
}}
```

## observe() function

```python
def observe(logger, level, component, action, **details) -> None
```

Every significant operation calls `observe()` with:
- `component`: subsystem name (`http`, `api`, `retrieval`, `qdrant`, `graph_store`)
- `action`: operation name (`request.started`, `search.completed`, `kb.created`)
- `**details`: arbitrary key-value context

## Event catalog

Events currently emitted by the backend:

### HTTP layer
| Event | Component | Details |
|-------|-----------|---------|
| `http.request.started` | http | method, path, query |
| `http.request.completed` | http | method, path, status_code, elapsed_ms |
| `http.request.failed` | http | method, path, elapsed_ms |

### API endpoints
| Event | Component | Details |
|-------|-----------|---------|
| `api.health.responded` | api | indexed_chunks, llm_provider, embedding_provider |
| `api.kb.created` | api | kb_id |
| `api.kb.listed` | api | count |
| `api.kb.renamed` | api | kb_id |
| `api.kb.deleted` | api | kb_id |
| `api.upload.completed` | api | kb_id, files |
| `api.documents.listed` | api | kb_id, count |
| `api.document.deleted` | api | kb_id, document_id |
| `api.graph.responded` | api | kb_id, nodes, edges, mentions |
| `api.graph.node_detail.responded` | api | kb_id, entity_id, mentions, documents, relations |
| `api.chat.context.ready` | api | kb_id, top_k, matches, search_query |
| `api.chat.stream.completed` | api | kb_id, source_count, elapsed_ms |

### Retrieval
| Event | Component | Details |
|-------|-----------|---------|
| `retrieval.query_expansion.completed` | retrieval | kb_id, matched_entities, added_terms, expanded_query |
| `retrieval.dense.completed` | retrieval | kb_id, matches |
| `retrieval.sparse.completed` | retrieval | kb_id, matches |
| `retrieval.graph_retrieval.candidates_found` | retrieval | kb_id, seeds, candidates, materialized |
| `retrieval.fusion.completed` | retrieval | kb_id, dense_matches, sparse_matches, graph_matches, fused_unique |

### Qdrant
| Event | Component | Details |
|-------|-----------|---------|
| `qdrant.client.created` | qdrant | url |
| `qdrant.search.completed` | qdrant | kb_id, matches, elapsed_ms |
| `qdrant.upsert.completed` | qdrant | kb_id, points |
| `qdrant.delete.completed` | qdrant | kb_id, count |

### Graph store (SQLite)
| Event | Component | Details |
|-------|-----------|---------|
| `graph_store.entity_lookup.completed` | graph_store | kb_id, terms, matches |
| `graph_store.neighbor_labels_found` | graph_store | kb_id, entity_count, labels |
| `graph_store.chunk_candidates_found` | graph_store | kb_id, entity_count, candidates |

## How to use

### Local debugging
```bash
# Set debug mode
export APP_ENV=debug

# Start backend
cd backend && uv run uvicorn api.main:app --reload

# Make a request (note the X-Request-ID in response headers)
curl -s -D - http://localhost:8000/health | jq

# For /chat, the NDJSON stream will include a final "debug" event
# with the full trace timeline when APP_ENV=debug
```

### Production
```bash
APP_ENV=production
# Logs will contain only WARNING and above.
# Pipe JSON logs to your aggregator (Loki, ELK, CloudWatch, etc.)
```

## Current gaps

This is an intentionally minimal observability setup. The following are
not yet implemented:

| Gap | Impact |
|-----|--------|
| **Metrics (Prometheus/OpenTelemetry)** | No request rate, latency histograms, error rate, or retrieval hit counts |
| **Distributed tracing** | No span propagation to Qdrant, Ollama/OpenAI, or between services |
| **Log shipping** | JSON is emitted to stdout; no built-in shipping to Loki/ELK/Cloud |
| **Sampling** | Trace collector is all-or-nothing per `APP_ENV`; no sampling for high-traffic scenarios |
| **LLM/Embedding instrumentation** | Provider calls (Ollama, OpenAI) are not individually traced |
| **Background task tracing** | Ingestion background tasks do not carry request context |

## Future directions

1. **Prometheus endpoint** — expose `/metrics` with request count, latency,
   retrieval matches, and ingestion counters.
2. **OpenTelemetry spans** — wrap Qdrant, LLM, and embedding calls with
   OTEL spans for end-to-end distributed tracing.
3. **Log shipping config** — document how to pipe JSON stdout to Fluentd,
   Vector, or directly to cloud log collectors.
4. **Sampled tracing** — add percentage-based sampling so debug-level
   trace collection is feasible in production.
5. **Provider instrumentation** — add `observe()` calls in
   `backend/providers/` for LLM and embedding request/response cycles.
