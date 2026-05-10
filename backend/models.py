from __future__ import annotations

from typing import Literal

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


class ExtractedEntity(BaseModel):
    label: str = Field(min_length=1)
    canonical_id: str = Field(min_length=1)
    entity_type: str = "concept"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ExtractedRelation(BaseModel):
    source: ExtractedEntity
    target: ExtractedEntity
    predicate: str = Field(min_length=1)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


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


class GraphEvidence(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    page: int | None = None
    section: str | None = None
    snippet: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class GraphNode(BaseModel):
    id: str
    label: str
    entity_type: str
    mentions: int = 0


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    predicate: str
    weight: int = 1
    evidence: list[GraphEvidence] = Field(default_factory=list)


class GraphStats(BaseModel):
    nodes: int = 0
    edges: int = 0
    mentions: int = 0


class GraphSnapshot(BaseModel):
    kb_id: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    stats: GraphStats = Field(default_factory=GraphStats)


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


class DeleteStoreResult(BaseModel):
    store: str
    status: Literal["deleted", "already_absent", "failed"]
    detail: str | None = None


class KnowledgeBaseDeleteResult(BaseModel):
    kb_id: str
    status: Literal["ok", "partial_failure"]
    stores: list[DeleteStoreResult] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    llm_provider: str
    embedding_provider: str
    indexed_chunks: int
