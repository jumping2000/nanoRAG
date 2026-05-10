from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agents.knowledge_agent import KnowledgeAgent
from agents.orchestrator import OrchestratorAgent
from chunking.structural_chunker import StructuralChunker
from config import get_settings
from models import ChatRequest, HealthResponse, SourceCitation
from providers.embedding_provider import EmbeddingProvider
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
ingestion_service = IngestionService(settings, chunker, dense_retriever, sparse_retriever)
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


@app.post("/upload")
async def upload(files: list[UploadFile] = File(...)) -> dict[str, object]:
    uploaded = [await ingestion_service.ingest_upload(file) for file in files]
    return {"uploaded": [item.model_dump() for item in uploaded]}


@app.post("/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    plan = orchestrator.plan(request.message)
    chunks = hybrid_retriever.search(plan.search_query, request.top_k)
    sources = [
        SourceCitation(
            chunk_id=chunk.chunk_id,
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
