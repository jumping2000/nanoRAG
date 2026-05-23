# MCP Server

nanoRAG exposes a Model Context Protocol (MCP) server that lets external AI agents query knowledge bases, retrieve documents, inspect knowledge graphs, and chat against indexed content.

## Quick start

### Local development

```bash
cd backend
uv sync
uv run mcp dev mcp_server.py
```

### Docker

```bash
docker compose up -d mcp
```

The MCP server listens on `http://localhost:8100/mcp` with streamable HTTP transport.

### Connect from Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "nanoRAG": {
      "transport": "streamable-http",
      "url": "http://localhost:8100/mcp"
    }
  }
}
```

### Connect from VS Code Copilot

Add to `.vscode/mcp.json` or the Copilot MCP settings:

```json
{
  "mcpServers": {
    "nanoRAG": {
      "transport": "streamable-http",
      "url": "http://localhost:8100/mcp"
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
FastMCP (streamable HTTP, port 8100)
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
