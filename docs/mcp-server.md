# MCP Server

nanoRAG exposes a Model Context Protocol (MCP) server that lets external AI agents query knowledge bases, retrieve documents, inspect knowledge graphs, and chat against indexed content.

## Quick start

### Local development

```bash
cd backend
uv run api.main:app --reload
```

### Docker

Run the backend service; the backend will start MCP as a subprocess and expose `/mcp` over HTTP.

```bash
docker compose up -d backend
```

The backend provides an HTTP proxy at `http://localhost:8000/mcp` (streamable HTTP for external clients).

### Debug / standalone MCP

If you need to run the MCP server by itself for debugging, you can start the MCP process directly. This runs the FastMCP app using the `stdio` transport and is useful when developing MCP tools:

```bash
# from repository root
python backend/mcp_server_start.py
```

Alternatively run the backend (which will start the MCP subprocess for you):

```bash
cd backend
uv run api.main:app --reload
```

Example: call `nanorag_chat` via the backend proxy (non-streaming JSON response):

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"kb_id":"arch-new","message":"fai un breve riassunto della architettura soa"}' \
  http://localhost:8000/mcp/nanorag_chat
```

Example: request a streaming NDJSON response (accept header):

```bash
curl -X POST \
  -H "Accept: application/x-ndjson" \
  -H "Content-Type: application/json" \
  -d '{"kb_id":"arch-new","message":"fai un breve riassunto della architettura soa"}' \
  http://localhost:8000/mcp/nanorag_chat
```

### Connect from Claude Desktop

Add to `claude_desktop_config.json` (point to the backend proxy):

```json
{
  "mcpServers": {
    "nanoRAG": {
      "transport": "stdio",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Connect from VS Code Copilot

Add to `.vscode/mcp.json` or the Copilot MCP settings (point to the backend proxy):

```json
{
  "mcpServers": {
    "nanoRAG": {
      "transport": "stdio",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

## Available tools

### `nanorag_health`

Check backend status and indexed chunk count.

**Input:** none

**Output:**

| Field | Type | Description |
| --- | --- | --- |
| status | str | Always `"ok"` when healthy |
| llm_provider | str | Active LLM provider |
| embedding_provider | str | Active embedding provider |
| indexed_chunks | int | Total chunks across all KBs |

### `nanorag_list_kbs`

List all knowledge bases with document and chunk counts.

**Input:** none

**Output:** list of:

| Field | Type | Description |
| --- | --- | --- |
| id | str | KB identifier |
| name | str | Human-readable KB name |
| documents | int | Document count |
| chunks | int | Chunk count |

### `nanorag_list_documents`

List documents in one knowledge base.

**Input:**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| kb_id | str | yes | Knowledge base identifier |

**Output:** list of:

| Field | Type | Description |
| --- | --- | --- |
| document_id | str | Document identifier |
| filename | str | Original filename |
| chunk_count | int | Number of chunks |
| created_at | str | ISO timestamp |

### `nanorag_get_graph`

Get the knowledge graph snapshot for a KB.

**Input:**

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| kb_id | str | yes | — | Knowledge base identifier |
| limit | int | no | 18 | Max nodes/edges returned |
| min_weight | int | no | 1 | Minimum edge weight filter |

**Output:** Graph snapshot with `kb_id`, `nodes`, `edges`, and `stats`.

### `nanorag_get_node_detail`

Get detailed evidence and relations for one graph entity.

**Input:**

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| kb_id | str | yes | — | Knowledge base identifier |
| entity_id | str | yes | — | Canonical entity ID |
| evidence_limit | int | no | 12 | Max evidence entries |

**Output:** Node detail with `node`, `relations`, `documents`, and `stats`. Returns `{"error": "..."}` when the entity is not found.

### `nanorag_chat`

Chat against a knowledge base with grounded answers and source citations. The tool uses the same retrieval pipeline (orchestrator → dense + sparse + RRF → knowledge agent) as the REST API.

**Input:**

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| kb_id | str | yes | — | Knowledge base identifier |
| message | str | yes | — | User question |
| top_k | int | no | 6 | Max chunks to retrieve |

**Output:**

| Field | Type | Description |
| --- | --- | --- |
| answer | str | Grounded Markdown answer |
| sources | list | Source citations with chunk and document metadata |
| search_query | str | Query used for retrieval |

### `nanorag_upload_document`

Upload a document into a knowledge base.

**Input:**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| kb_id | str | yes | Target knowledge base |
| file_content | bytes | yes | Raw file content |
| filename | str | no | Original filename |

**Output:**

| Field | Type | Description |
| --- | --- | --- |
| document_id | str | Generated document ID |
| filename | str | Original filename |
| ingested_chunks | int | Chunks created |

### `nanorag_delete_document`

Remove one document and all its indexed data from a KB.

**Input:**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| kb_id | str | yes | Knowledge base identifier |
| document_id | str | yes | Document to delete |

**Output:**

| Field | Type | Description |
| --- | --- | --- |
| status | str | `"ok"` on success |

## Architecture

The MCP server shares the same runtime singletons as the FastAPI backend:

```
MCP Agent Client
  ↓
Backend `/mcp` HTTP proxy (port 8000) → forwards to MCP subprocess (stdio)
  ↓
build_ingestion_runtime(settings)
    ├── DenseRetriever
    ├── SparseRetriever
    ├── HybridRetriever
    ├── GraphStore
    ├── MetadataCatalog
    ├── IngestionService
    ├── OrchestratorAgent
    └── KnowledgeAgent
```

This means:
- The MCP server uses the same Qdrant collection, same local metadata, and same graph store as the REST API
- No duplicated retrieval or ingestion logic
- The same LLM and embedding providers are used

## File layout

```
backend/
  mcp_server.py           FastMCP app with tool definitions and shared runtime
  mcp_server_start.py     Standalone entry point for uvicorn
  tests/
    test_mcp_server.py    MCP-specific tests
```

## Testing

```bash
cd backend
uv run pytest tests/test_mcp_server.py -v
```

The test suite uses fake runtime components to verify tool contracts without requiring Qdrant or Ollama.

## Limitations

- `nanorag_chat` collects the full answer synchronously before returning (no streaming in the first slice)
- `nanorag_upload_document` accepts raw bytes (`file_content`) rather than file paths, for security
- KB creation and deletion are not exposed as MCP tools in the first slice
- The MCP server runs as a separate process from the FastAPI backend; both share the same `backend/data` volume for local persistence and the same Qdrant service
