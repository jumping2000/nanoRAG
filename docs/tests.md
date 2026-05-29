# nanoRAG — Test Suite Reference

18 test files · 66 test cases · run command: `uv run python -m pytest -q`

## Running Tests

```bash
cd backend
uv run python -m pytest -q                        # all tests
uv run python -m pytest -v tests/test_mcp_proxy.py  # single file
uv run python -m pytest -m "not integration"      # skip integration tests
```

## Test Files

### MCP & Proxy

| File | Cases | Description |
|------|-------|-------------|
| `test_mcp_server.py` | 8 | MCP tool contract: health, list_kbs, chat, upload, delete, get_graph, get_node_detail |
| `test_mcp_proxy.py` | 14 | `/mcp` proxy: auth, stdio bridge (stream/non‑stream, errors), streamable‑http forwarding (GET/POST mocks, `MCP_HTTP_PORT`, `MCP_HTTP_URL` override) |
| `test_proxy.py` | 2 | **End‑to‑end integration** (skipped by default): initialize session + `nanorag_health` tool call via live proxy. Requires running MCP server + backend |

### Knowledge Graph

| File | Cases | Description |
|------|-------|-------------|
| `test_graph.py` | 4 | GraphStore: snapshot, KB/document isolation, node detail, delete |
| `test_graph_extraction.py` | 6 | Entity/relation extraction: structured JSON parsing, fallback, schema variants, LLM credentials |
| `test_graph_reranker.py` | 4 | GraphReranker: promotes relation‑bearing chunks, stable tiebreakers, absent signal |
| `test_graph_benchmark.py` | 1 | Extractor comparison (structured vs base) |
| `test_graph_smoke_api.py` | 1 | Full API flow: create KB → upload → graph → delete |
| `test_graph_node_detail_api.py` | 1 | Node detail API: KB‑scoped relation isolation |

### Retrieval & Search

| File | Cases | Description |
|------|-------|-------------|
| `test_catalog_and_sparse.py` | 7 | Settings (app_env, graph extraction), MetadataCatalog, SparseRetriever (BM25, KB isolation) |
| `test_dense_search.py` | 1 | DenseRetriever: Qdrant `query_points` API compatibility |
| `test_fusion.py` | 2 | Reciprocal Rank Fusion, deterministic Qdrant point UUID |

### API & CRUD

| File | Cases | Description |
|------|-------|-------------|
| `test_document_deletion_api.py` | 1 | DELETE /kb/{kb_id}/documents/{doc_id}: document state cleanup |
| `test_kb_deletion.py` | 4 | DELETE /kb/{kb_id}: idempotency, partial failures, multi‑store cleanup, single document delete |
| `test_upload_graph_background.py` | 1 | Upload persists document before background graph extraction |

### Infrastructure

| File | Cases | Description |
|------|-------|-------------|
| `test_structural_chunker.py` | 1 | StructuralChunker: section metadata, paragraph‑based chunking |
| `test_maintenance.py` | 3 | Maintenance: rebuild from sparse chunks, purge orphan Qdrant points, reset all state |
| `test_observability.py` | 4 | HTTP headers per environment, debug trace events in chat stream, reranked chunk order |

## Available Markers

| Marker | Usage |
|--------|-------|
| `integration` | Tests requiring external services (MCP server, backend). Run with `-m "integration"` or skip with `-m "not integration"` |

## Conventions

- Tests use `pytest` + `pytest-asyncio` with `asyncio_mode = "auto"`
- Heavy dependency mocks (Qdrant, Ollama) are handled in the test file itself or via `monkeypatch`
- `conftest.py` provides the `clear_settings_cache` fixture to isolate environment variables across tests
- Temporary files use `tmp_path` (built‑in pytest fixture)
