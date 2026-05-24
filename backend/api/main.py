from __future__ import annotations

# MCP_SUBPROCESS_IMPORT_FIXED

import json
import logging
import time
from uuid import uuid4
from collections.abc import Iterator

from fastapi import BackgroundTasks,FastAPI, File, Query, Request, UploadFile
import os
import json
import asyncio
from fastapi.responses import StreamingResponse, JSONResponse
from mcp_subprocess import AsyncMCPSubprocess
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agents.knowledge_agent import KnowledgeAgent
from agents.orchestrator import OrchestratorAgent
from bootstrap import build_ingestion_runtime
from config import get_settings
from models import (
    ChatRequest,
    DeleteResponse,
    GraphNodeDetail,
    GraphSnapshot,
    HealthResponse,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseUpdateRequest,
    SourceCitation,
)
from retrieval.graph_reranker import GraphReranker
from retrieval.hybrid_search import HybridRetriever
from observability import (
    bind_request_context,
    clear_request_context,
    configure_logging,
    current_request_id,
    current_trace,
    observe,
    reset_request_context,
    start_request_context,
)

settings = get_settings()
configure_logging(settings)
logger = logging.getLogger(__name__)
runtime = build_ingestion_runtime(settings)
dense_retriever = runtime.dense_retriever
sparse_retriever = runtime.sparse_retriever
hybrid_retriever = HybridRetriever(settings, dense_retriever, sparse_retriever)
catalog = runtime.catalog
graph_store = runtime.graph_store
graph_reranker = GraphReranker(
    graph_store,
    min_confidence=settings.graph_extraction_min_confidence,
)
ingestion_service = runtime.ingestion_service
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


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    context_tokens, trace_collector = start_request_context(request_id=request_id, settings=settings)
    start = time.perf_counter()
    observe(
        logger,
        logging.INFO,
        "http",
        "request.started",
        method=request.method,
        path=request.url.path,
        query=request.url.query or None,
    )

    try:
        response = await call_next(request)
    except Exception:
        observe(
            logger,
            logging.ERROR,
            "http",
            "request.failed",
            method=request.method,
            path=request.url.path,
            elapsed_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        reset_request_context(context_tokens)
        raise

    response.headers["X-Request-ID"] = request_id
    if settings.enable_deep_observability:
        response.headers["X-Debug-Trace-Mode"] = settings.environment
    if trace_collector is not None:
        response.headers["X-Debug-Trace-Events"] = str(len(trace_collector.events))

    observe(
        logger,
        logging.INFO,
        "http",
        "request.completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        elapsed_ms=round((time.perf_counter() - start) * 1000, 2),
    )
    reset_request_context(context_tokens)
    return response


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    observe(
        logger,
        logging.INFO,
        "api",
        "health.responded",
        indexed_chunks=ingestion_service.indexed_chunks(),
        llm_provider=settings.llm_provider,
        embedding_provider=settings.embedding_provider,
    )
    return HealthResponse(
        status="ok",
        llm_provider=settings.llm_provider,
        embedding_provider=settings.embedding_provider,
        indexed_chunks=ingestion_service.indexed_chunks(),
    )


@app.post("/kb")
def create_kb(request: KnowledgeBaseCreateRequest) -> dict[str, object]:
    kb = catalog.create_kb(kb_id=request.id, name=request.name)
    observe(logger, logging.INFO, "api", "kb.created", kb_id=kb.id)
    return kb.model_dump()


@app.get("/kb")
def list_kbs() -> list[dict[str, object]]:
    kb_list = [kb.model_dump() for kb in catalog.list_kbs()]
    observe(logger, logging.INFO, "api", "kb.listed", count=len(kb_list))
    return kb_list


@app.patch("/kb/{kb_id}")
def rename_kb(kb_id: str, request: KnowledgeBaseUpdateRequest) -> dict[str, object]:
    kb = catalog.rename_kb(kb_id, request.name)
    observe(logger, logging.INFO, "api", "kb.renamed", kb_id=kb_id)
    return kb.model_dump()


@app.delete("/kb/{kb_id}", response_model=DeleteResponse)
def delete_kb(kb_id: str) -> DeleteResponse:
    ingestion_service.delete_kb(kb_id)
    observe(logger, logging.INFO, "api", "kb.deleted", kb_id=kb_id)
    return DeleteResponse()


@app.post("/kb/{kb_id}/upload")
async def upload(
    kb_id: str,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
) -> dict[str, object]:
    uploaded = [
        await ingestion_service._ingest_upload(kb_id, file, background_tasks=background_tasks)
        for file in files
    ]
    observe(
        logger,
        logging.INFO,
        "api",
        "upload.completed",
        kb_id=kb_id,
        files=len(uploaded),
    )
    return {"uploaded": [item.model_dump() for item in uploaded]}


@app.get("/kb/{kb_id}/documents")
def list_documents(kb_id: str) -> list[dict[str, object]]:
    documents = [document.model_dump() for document in ingestion_service.list_documents(kb_id)]
    observe(logger, logging.INFO, "api", "documents.listed", kb_id=kb_id, count=len(documents))
    return documents


@app.get("/kb/{kb_id}/graph", response_model=GraphSnapshot)
def get_graph(
    kb_id: str,
    limit: int = Query(default=18, ge=1, le=64),
    min_weight: int = Query(default=1, ge=1, le=10),
) -> GraphSnapshot:
    catalog.get_kb(kb_id)
    snapshot = graph_store.get_snapshot(kb_id=kb_id, limit=limit, min_weight=min_weight)
    observe(
        logger,
        logging.INFO,
        "api",
        "graph.responded",
        kb_id=kb_id,
        nodes=snapshot.stats.nodes,
        edges=snapshot.stats.edges,
        mentions=snapshot.stats.mentions,
    )
    return snapshot


@app.get("/kb/{kb_id}/graph/node/{entity_id}", response_model=GraphNodeDetail)
def get_graph_node_detail(
    kb_id: str,
    entity_id: str,
    evidence_limit: int = Query(default=12, ge=1, le=24),
) -> GraphNodeDetail:
    catalog.get_kb(kb_id)
    detail = graph_store.get_node_detail(kb_id=kb_id, entity_id=entity_id, evidence_limit=evidence_limit)
    observe(
        logger,
        logging.INFO,
        "api",
        "graph.node_detail.responded",
        kb_id=kb_id,
        entity_id=entity_id,
        mentions=detail.stats.get("mentions", 0),
        documents=detail.stats.get("documents", 0),
        relations=detail.stats.get("relations", 0),
    )
    return detail


@app.delete("/kb/{kb_id}/documents/{document_id}", response_model=DeleteResponse)
def delete_document(kb_id: str, document_id: str) -> DeleteResponse:
    ingestion_service.delete_document(kb_id, document_id)
    observe(logger, logging.INFO, "api", "document.deleted", kb_id=kb_id, document_id=document_id)
    return DeleteResponse()


@app.post("/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    catalog.get_kb(request.kb_id)
    plan = orchestrator.plan(request.message)
    chunks = hybrid_retriever.search(plan.search_query, kb_id=request.kb_id, top_k=request.top_k)
    chunks = graph_reranker.rerank(request.kb_id, chunks)
    observe(
        logger,
        logging.INFO,
        "api",
        "chat.context.ready",
        kb_id=request.kb_id,
        top_k=request.top_k or settings.retrieval_top_k,
        needs_retrieval=plan.needs_retrieval,
        matches=len(chunks),
        search_query=plan.search_query,
    )
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
    request_id = current_request_id()
    trace_collector = current_trace()

    def event_stream() -> Iterator[str]:
        bind_request_context(
            request_id=request_id,
            environment=settings.environment,
            trace_collector=trace_collector,
        )
        started = time.perf_counter()
        yield _event({"type": "meta", "searchQuery": plan.search_query, "matches": len(chunks)})
        try:
            for token in knowledge_agent.stream_answer(request.message, plan, chunks):
                yield _event({"type": "token", "content": token})
            yield _event({"type": "sources", "sources": [item.model_dump() for item in sources]})
            observe(
                logger,
                logging.INFO,
                "api",
                "chat.stream.completed",
                kb_id=request.kb_id,
                source_count=len(sources),
                elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            if trace_collector is not None:
                yield _event({"type": "debug", "trace": trace_collector.snapshot()})
            yield _event({"type": "done"})
        finally:
            clear_request_context()

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


def _event(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


# ---- MCP stdio bridge: start subprocess and proxy /mcp requests ----
mcp_manager: AsyncMCPSubprocess | None = None


@app.on_event("startup")
async def _start_mcp_subprocess():
    global mcp_manager
    mcp_manager = AsyncMCPSubprocess()
    await mcp_manager.start()


@app.on_event("shutdown")
async def _stop_mcp_subprocess():
    global mcp_manager
    if mcp_manager is not None:
        await mcp_manager.stop()


@app.api_route('/mcp/{path:path}', methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def mcp_proxy(path: str, request: Request):
    """Proxy HTTP requests to MCP subprocess over stdio.

    Expects MCP messages framed as NDJSON with an `id` field. Authorization via `X-API-Key` header.
    """
    api_key = os.getenv('MCP_API_KEY')
    header = request.headers.get('x-api-key')
    if api_key and header != api_key:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    if mcp_manager is None:
        return JSONResponse(status_code=503, content={"detail": "MCP subprocess not started"})

    # Determine tool name and params
    tool_name = path.strip('/') or 'nanorag_health'
    params = {}
    if request.method in ("POST", "PUT", "PATCH"):
        try:
            raw_body = await request.body()
            params = json.loads(raw_body) if raw_body else {}
        except Exception:
            params = {}
    else:
        params = dict(request.query_params)

    accept = request.headers.get('accept', '')
    stream = 'application/x-ndjson' in accept

    try:
        if stream:
            agen = await mcp_manager.call_tool(tool_name, params, stream=True)
            return StreamingResponse(agen, media_type='application/x-ndjson')
        else:
            res = await mcp_manager.call_tool(tool_name, params, stream=False)
            # If the subprocess returned an object with 'result', unwrap it
            if isinstance(res, dict) and 'result' in res:
                return JSONResponse(content=res['result'])
            return JSONResponse(content=res)
    except Exception as exc:
        return JSONResponse(status_code=502, content={"detail": str(exc)})
