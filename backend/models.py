from __future__ import annotations

from pydantic import BaseModel, Field


class ChunkMetadata(BaseModel):
    chunk_id: str
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
    filename: str
    page: int | None = None
    section: str | None = None
    score: float = 0.0


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)


class UploadResponse(BaseModel):
    filename: str
    ingested_chunks: int


class HealthResponse(BaseModel):
    status: str
    llm_provider: str
    embedding_provider: str
    indexed_chunks: int
