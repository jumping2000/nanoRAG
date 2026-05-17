# API

## Response headers

All endpoints return `X-Request-ID`.

When the backend runs with `APP_ENV=development` or `APP_ENV=debug`, responses also include `X-Debug-Trace-Mode`.

When the backend runs with `APP_ENV=debug`, responses may additionally include `X-Debug-Trace-Events` with the current trace event count.

## `GET /health`

Returns basic service status.

Example response:

```json
{
  "status": "ok",
  "llm_provider": "openai",
  "embedding_provider": "openai",
  "indexed_chunks": 42
}
```

## `POST /kb`

Create a new knowledge base.

Request body:

```json
{
  "id": "finance",
  "name": "Finance"
}
```

## `GET /kb`

List available knowledge bases.

Example response:

```json
[
  {
    "id": "finance",
    "name": "Finance",
    "documents": 3,
    "chunks": 41
  }
]
```

## `PATCH /kb/{id}`

Rename an existing knowledge base.

Request body:

```json
{
  "name": "Finance & Risk"
}
```

## `DELETE /kb/{id}`

Delete a knowledge base and all its indexed chunks.

## `POST /kb/{id}/upload`

Multipart upload for one or more documents.

Supported formats:

- PDF
- TXT
- Markdown

Example response:

```json
{
  "uploaded": [
    {
      "document_id": "finance-risk-report-1a2b3c4d5e6f",
      "filename": "architecture.pdf",
      "ingested_chunks": 18
    }
  ]
}
```

Only chunk metadata and KB/document catalog records are persisted. Raw uploaded PDF/TXT/MD files are processed in-memory and discarded.

## `GET /kb/{id}/documents`

List documents belonging to one knowledge base.

Example response:

```json
[
  {
    "document_id": "finance-risk-report-1a2b3c4d5e6f",
    "kb_id": "finance",
    "kb_name": "Finance",
    "filename": "risk_report.pdf",
    "chunk_count": 18,
    "created_at": "2026-05-10T18:00:00+00:00"
  }
]
```

## `DELETE /kb/{id}/documents/{doc_id}`

Delete one indexed document and all of its chunks.

## `POST /chat`

Request body:

```json
{
  "message": "Explain the SOA backplane architecture",
  "kb_id": "finance",
  "top_k": 6
}
```

Response media type:

- `application/x-ndjson`

Possible event stream frames:

```json
{"type":"meta","searchQuery":"SOA backplane architecture","matches":6}
{"type":"token","content":"The architecture ..."}
{"type":"sources","sources":[{"chunk_id":"...","kb_id":"finance","document_id":"finance-risk-report-1a2b3c4d5e6f","filename":"doc.pdf","page":3,"section":"Overview","score":0.03}]}
{"type":"debug","trace":{"requestId":"...","environment":"debug","elapsedMs":42.5,"events":[{"at":"2026-05-17T12:00:00+00:00","component":"api","action":"chat.context.ready","details":{"kb_id":"finance","matches":6}}]}}
{"type":"done"}
```

The `debug` event is emitted only when `APP_ENV=debug`.
