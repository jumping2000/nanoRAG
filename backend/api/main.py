from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import FastAPI, File, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agents.knowledge_agent import KnowledgeAgent
from agents.orchestrator import OrchestratorAgent
from chunking.structural_chunker import StructuralChunker
from config import get_settings
from models import (
    ChatRequest,
    DeleteResponse,
    GraphSnapshot,
    HealthResponse,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseUpdateRequest,
    SourceCitation,
)
from providers.embedding_provider import EmbeddingProvider
from rag.catalog import MetadataCatalog
from rag.graph_extractor import GraphExtractor
from rag.graph_store import GraphStore
from rag.ingest import IngestionService
from retrieval.dense_search import DenseRetriever
from retrieval.hybrid_search import HybridRetriever
from retrieval.sparse_search import SparseRetriever

settings = get_settings()
embedding_provider = EmbeddingProvider(settings)
dense_retriever = DenseRetriever(settings, embedding_provider)
sparse_retriever = SparseRetriever(settings)
hybrid_retriever = HybridRetriever(settings, dense_retriever, sparse_retriever)
chunker = StructuralChunker(settings.chunk_size_tokens, settings.chunk_overlap_tokens)
catalog = MetadataCatalog(settings)
graph_extractor = GraphExtractor()
graph_store = GraphStore(settings)
ingestion_service = IngestionService(
    settings,
    chunker,
    dense_retriever,
    sparse_retriever,
    catalog,
    graph_extractor,
    graph_store,
)
orchestrator = OrchestratorAgent(settings)
knowledge_agent = KnowledgeAgent(settings)

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        llm_provider=settings.llm_provider,
        embedding_provider=settings.embedding_provider,
        indexed_chunks=ingestion_service.indexed_chunks(),
    )


@app.post("/kb")
def create_kb(request: KnowledgeBaseCreateRequest) -> dict[str, object]:
    kb = catalog.create_kb(kb_id=request.id, name=request.name)
    return kb.model_dump()


@app.get("/kb")
def list_kbs() -> list[dict[str, object]]:
    return [kb.model_dump() for kb in catalog.list_kbs()]


@app.patch("/kb/{kb_id}")
def rename_kb(kb_id: str, request: KnowledgeBaseUpdateRequest) -> dict[str, object]:
    kb = catalog.rename_kb(kb_id, request.name)
    return kb.model_dump()


@app.delete("/kb/{kb_id}", response_model=DeleteResponse)
def delete_kb(kb_id: str) -> DeleteResponse:
    ingestion_service.delete_kb(kb_id)
    return DeleteResponse()


@app.post("/kb/{kb_id}/upload")
async def upload(kb_id: str, files: list[UploadFile] = File(...)) -> dict[str, object]:
    uploaded = [await ingestion_service.ingest_upload(kb_id, file) for file in files]
    return {"uploaded": [item.model_dump() for item in uploaded]}


@app.get("/kb/{kb_id}/documents")
def list_documents(kb_id: str) -> list[dict[str, object]]:
    return [document.model_dump() for document in ingestion_service.list_documents(kb_id)]


@app.get("/kb/{kb_id}/graph", response_model=GraphSnapshot)
def get_graph(
    kb_id: str,
    limit: int = Query(default=18, ge=1, le=64),
    min_weight: int = Query(default=1, ge=1, le=10),
) -> GraphSnapshot:
    catalog.get_kb(kb_id)
    return graph_store.get_snapshot(kb_id=kb_id, limit=limit, min_weight=min_weight)


@app.delete("/kb/{kb_id}/documents/{document_id}", response_model=DeleteResponse)
def delete_document(kb_id: str, document_id: str) -> DeleteResponse:
    ingestion_service.delete_document(kb_id, document_id)
    return DeleteResponse()


@app.post("/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    catalog.get_kb(request.kb_id)
    plan = orchestrator.plan(request.message)
    chunks = hybrid_retriever.search(plan.search_query, kb_id=request.kb_id, top_k=request.top_k)
    sources = [
        SourceCitation(
            chunk_id=chunk.chunk_id,
            kb_id=chunk.kb_id,
            document_id=chunk.document_id,
            filename=chunk.filename,
            page=chunk.page,
            section=chunk.section,
            score=chunk.score,
        )
        for chunk in chunks
    ]

    def event_stream() -> Iterator[str]:
        yield _event({"type": "meta", "searchQuery": plan.search_query, "matches": len(chunks)})
        for token in knowledge_agent.stream_answer(request.message, plan, chunks):
            yield _event({"type": "token", "content": token})
        yield _event({"type": "sources", "sources": [item.model_dump() for item in sources]})
        yield _event({"type": "done"})

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


def _event(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"
