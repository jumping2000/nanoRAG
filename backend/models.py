from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

GraphEntityType = Literal[
    "organization",
    "system",
    "service",
    "database",
    "person",
    "location",
    "artifact",
    "concept",
    "other",
]
GRAPH_ENTITY_TYPES: tuple[str, ...] = (
    "organization",
    "system",
    "service",
    "database",
    "person",
    "location",
    "artifact",
    "concept",
    "other",
)
GraphPredicate = Literal[
    "depends_on",
    "connects_to",
    "uses",
    "stores",
    "indexes",
    "retrieves_from",
    "runs_on",
    "belongs_to",
    "manages",
    "references",
    "related_to",
]
GRAPH_PREDICATES: tuple[str, ...] = (
    "depends_on",
    "connects_to",
    "uses",
    "stores",
    "indexes",
    "retrieves_from",
    "runs_on",
    "belongs_to",
    "manages",
    "references",
    "related_to",
)


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


class GraphExtractionEntity(BaseModel):
    label: str = Field(min_length=1)
    entity_type: GraphEntityType = "concept"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class GraphExtractionRelation(BaseModel):
    source_label: str = Field(min_length=1)
    target_label: str = Field(min_length=1)
    predicate: GraphPredicate
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class GraphExtractionResult(BaseModel):
    entities: list[GraphExtractionEntity] = Field(default_factory=list)
    relations: list[GraphExtractionRelation] = Field(default_factory=list)


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


class GraphNodeRelation(BaseModel):
    edge_id: str
    predicate: str
    direction: Literal["incoming", "outgoing"]
    counterpart: GraphNode
    weight: int = 1
    evidence: list[GraphEvidence] = Field(default_factory=list)


class GraphNodeDocument(BaseModel):
    document_id: str
    filename: str
    mention_count: int = 0


class GraphStats(BaseModel):
    nodes: int = 0
    edges: int = 0
    mentions: int = 0


class GraphSnapshot(BaseModel):
    kb_id: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    stats: GraphStats = Field(default_factory=GraphStats)


class GraphNodeDetail(BaseModel):
    node: GraphNode
    relations: list[GraphNodeRelation] = Field(default_factory=list)
    documents: list[GraphNodeDocument] = Field(default_factory=list)
    stats: dict[str, int] = Field(default_factory=dict)


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
