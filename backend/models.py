from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeBaseCreateRequest(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)


class KnowledgeBaseUpdateRequest(BaseModel):
    name: str = Field(min_length=1)


class KnowledgeBaseRecord(BaseModel):
    id: str
    name: str
    documents: int = 0
    chunks: int = 0


class DocumentRecord(BaseModel):
    document_id: str
    kb_id: str
    kb_name: str
    filename: str
    chunk_count: int
    created_at: str


class ChunkMetadata(BaseModel):
    chunk_id: str
    kb_id: str
    kb_name: str
    document_id: str
    source: str
    filename: str
    page: int | None = None
    section: str | None = None
    text: str
    token_count: int


class RetrievedChunk(ChunkMetadata):
    score: float = 0.0
    rank: int = 0


class SourceCitation(BaseModel):
    chunk_id: str
    kb_id: str
    document_id: str
    filename: str
    page: int | None = None
    section: str | None = None
    score: float = 0.0


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    kb_id: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)


class UploadResponse(BaseModel):
    document_id: str
    filename: str
    ingested_chunks: int


class DeleteResponse(BaseModel):
    status: str = "ok"


class HealthResponse(BaseModel):
    status: str
    llm_provider: str
    embedding_provider: str
    indexed_chunks: int
