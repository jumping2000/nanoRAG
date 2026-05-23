"""nanoRAG MCP Server — agentic knowledge base access via Model Context Protocol."""

from __future__ import annotations

from io import BytesIO

from fastapi import UploadFile
from mcp.server.fastmcp import FastMCP

from agents.knowledge_agent import KnowledgeAgent
from agents.orchestrator import OrchestratorAgent
from bootstrap import build_ingestion_runtime
from config import get_settings
from retrieval.hybrid_search import HybridRetriever

settings = get_settings()
runtime = build_ingestion_runtime(settings)
dense_retriever = runtime.dense_retriever
sparse_retriever = runtime.sparse_retriever
catalog = runtime.catalog
graph_store = runtime.graph_store
ingestion_service = runtime.ingestion_service
hybrid_retriever = HybridRetriever(settings, dense_retriever, sparse_retriever)
orchestrator = OrchestratorAgent(settings)
knowledge_agent = KnowledgeAgent(settings)

mcp = FastMCP(name="nanoRAG")


@mcp.tool()
def nanorag_health() -> dict:
    """Check nanoRAG backend health and indexed chunk count."""
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "embedding_provider": settings.embedding_provider,
        "indexed_chunks": ingestion_service.indexed_chunks(),
    }


@mcp.tool()
def nanorag_list_kbs() -> list[dict]:
    """List all available knowledge bases with document and chunk counts."""
    return [kb.model_dump() for kb in catalog.list_kbs()]


@mcp.tool()
def nanorag_list_documents(kb_id: str) -> list[dict]:
    """List all documents in the specified knowledge base."""
    return [
        document.model_dump() for document in ingestion_service.list_documents(kb_id)
    ]


@mcp.tool()
def nanorag_get_graph(kb_id: str, limit: int = 18, min_weight: int = 1) -> dict:
    """Get the knowledge graph snapshot for a knowledge base."""
    catalog.get_kb(kb_id)
    snapshot = graph_store.get_snapshot(kb_id=kb_id, limit=limit, min_weight=min_weight)
    return snapshot.model_dump()


@mcp.tool()
def nanorag_get_node_detail(
    kb_id: str, entity_id: str, evidence_limit: int = 12,
) -> dict:
    """Get detailed evidence and relations for one graph entity."""
    catalog.get_kb(kb_id)
    try:
        detail = graph_store.get_node_detail(
            kb_id=kb_id, entity_id=entity_id, evidence_limit=evidence_limit,
        )
        return detail.model_dump()
    except LookupError:
        return {"error": f"Graph node not found: {entity_id}"}


@mcp.tool()
def nanorag_chat(kb_id: str, message: str, top_k: int = 6) -> dict:
    """Chat against a knowledge base with grounded answers and source citations."""
    catalog.get_kb(kb_id)
    plan = orchestrator.plan(message)
    chunks = hybrid_retriever.search(plan.search_query, kb_id=kb_id, top_k=top_k)

    answer_parts: list[str] = []
    for token in knowledge_agent.stream_answer(message, plan, chunks):
        answer_parts.append(token)

    return {
        "answer": "".join(answer_parts),
        "sources": [
            {
                "chunk_id": chunk.chunk_id,
                "kb_id": chunk.kb_id,
                "document_id": chunk.document_id,
                "filename": chunk.filename,
                "page": chunk.page,
                "section": chunk.section,
                "score": chunk.score,
            }
            for chunk in chunks
        ],
        "search_query": plan.search_query,
    }


@mcp.tool()
def nanorag_upload_document(kb_id: str, file_content: bytes, filename: str = "document") -> dict:
    """Upload a document into a knowledge base and return ingestion metadata."""
    import asyncio

    upload = UploadFile(filename=filename, file=BytesIO(file_content))

    async def _ingest():
        return await ingestion_service._ingest_upload(kb_id, upload)

    result = asyncio.run(_ingest())
    return {
        "document_id": result.document_id,
        "filename": result.filename,
        "ingested_chunks": result.ingested_chunks,
    }


@mcp.tool()
def nanorag_delete_document(kb_id: str, document_id: str) -> dict:
    """Delete one document and all its indexed data from a knowledge base."""
    ingestion_service.delete_document(kb_id, document_id)
    return {"status": "ok"}
