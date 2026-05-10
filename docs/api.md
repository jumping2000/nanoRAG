# API

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

## `POST /upload`

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
      "filename": "architecture.pdf",
      "ingested_chunks": 18
    }
  ]
}
```

## `POST /chat`

Request body:

```json
{
  "message": "Explain the SOA backplane architecture",
  "top_k": 6
}
```

Response media type:

- `application/x-ndjson`

Possible event stream frames:

```json
{"type":"meta","searchQuery":"SOA backplane architecture","matches":6}
{"type":"token","content":"The architecture ..."}
{"type":"sources","sources":[{"chunk_id":"...","filename":"doc.pdf","page":3,"section":"Overview","score":0.03}]}
{"type":"done"}
```
