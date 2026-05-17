from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from chunking.structural_chunker import StructuralChunker
from config import Settings
from db.qdrant import (
    create_qdrant_client,
    delete_collection,
    delete_points_by_ids,
    list_orphan_point_ids,
)
from models import DocumentRecord, KnowledgeBaseDeleteResult
from observability import observe
from providers.embedding_provider import EmbeddingProvider
from rag.catalog import MetadataCatalog
from rag.graph_extractor import GraphExtractor
from rag.graph_store import GraphStore
from rag.ingest import IngestionService
from retrieval.dense_search import DenseRetriever
from retrieval.sparse_search import SparseRetriever

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class RebuildKbSummary:
    kb_id: str
    kb_name: str
    documents: int
    chunks: int


@dataclass(slots=True, frozen=True)
class ResetAllSummary:
    uploads_deleted: int
    qdrant_collection_deleted: bool


def delete_kb_totally(settings: Settings, kb_id: str) -> KnowledgeBaseDeleteResult:
    service = _build_ingestion_service(settings)
    result = service.delete_kb(kb_id)
    observe(logger, logging.INFO, "maintenance", "kb.deleted", kb_id=kb_id)
    return result


def rebuild_kb_from_sparse_chunks(settings: Settings, kb_id: str) -> RebuildKbSummary:
    sparse_retriever = SparseRetriever(settings)
    chunks = sparse_retriever.list_chunks(kb_id)
    if not chunks:
        raise ValueError(f"No sparse chunks found for knowledge base: {kb_id}")

    catalog = MetadataCatalog(settings)
    kb_name = chunks[0].kb_name or kb_id
    catalog.upsert_kb(kb_id, kb_name)

    created_at = datetime.now(UTC).isoformat()
    documents_by_id: dict[str, DocumentRecord] = {}
    chunk_counts: dict[str, int] = {}
    for chunk in chunks:
        chunk_counts[chunk.document_id] = chunk_counts.get(chunk.document_id, 0) + 1
        if chunk.document_id not in documents_by_id:
            documents_by_id[chunk.document_id] = DocumentRecord(
                document_id=chunk.document_id,
                kb_id=kb_id,
                kb_name=kb_name,
                filename=chunk.filename,
                chunk_count=0,
                created_at=created_at,
            )

    rebuilt_documents = [
        documents_by_id[document_id].model_copy(update={"chunk_count": chunk_counts[document_id]})
        for document_id in sorted(documents_by_id)
    ]
    catalog.replace_documents(kb_id, rebuilt_documents)
    observe(
        logger,
        logging.INFO,
        "maintenance",
        "kb.rebuilt",
        kb_id=kb_id,
        documents=len(rebuilt_documents),
        chunks=len(chunks),
    )
    return RebuildKbSummary(
        kb_id=kb_id,
        kb_name=kb_name,
        documents=len(rebuilt_documents),
        chunks=len(chunks),
    )


def purge_orphan_qdrant_points(settings: Settings, client=None) -> int:
    qdrant_client = client or create_qdrant_client(settings)
    orphan_ids = list_orphan_point_ids(qdrant_client, settings.qdrant_collection)
    deleted = delete_points_by_ids(qdrant_client, settings.qdrant_collection, orphan_ids)
    observe(logger, logging.INFO, "maintenance", "qdrant.orphans_purged", deleted=deleted)
    return deleted


def reset_all_state(settings: Settings, client=None) -> ResetAllSummary:
    qdrant_client = client or create_qdrant_client(settings)

    settings.knowledge_bases_store_path.write_text("{}", encoding="utf-8")
    settings.documents_store_path.write_text("[]", encoding="utf-8")
    settings.chunks_store_path.write_text("", encoding="utf-8")

    uploads_deleted = _clear_uploads(settings.uploads_dir)
    if settings.graph_store_path.exists():
        settings.graph_store_path.unlink()

    collection_deleted = delete_collection(qdrant_client, settings.qdrant_collection)
    observe(
        logger,
        logging.INFO,
        "maintenance",
        "state.reset",
        uploads_deleted=uploads_deleted,
        qdrant_collection_deleted=collection_deleted,
    )
    return ResetAllSummary(
        uploads_deleted=uploads_deleted,
        qdrant_collection_deleted=collection_deleted,
    )


def _clear_uploads(uploads_dir: Path) -> int:
    uploads_dir.mkdir(parents=True, exist_ok=True)
    deleted = 0
    for child in uploads_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
        deleted += 1
    return deleted


def _build_ingestion_service(settings: Settings) -> IngestionService:
    embedding_provider = EmbeddingProvider(settings)
    dense_retriever = DenseRetriever(settings, embedding_provider)
    sparse_retriever = SparseRetriever(settings)
    chunker = StructuralChunker(settings.chunk_size_tokens, settings.chunk_overlap_tokens)
    catalog = MetadataCatalog(settings)
    graph_extractor = GraphExtractor()
    graph_store = GraphStore(settings)
    return IngestionService(
        settings,
        chunker,
        dense_retriever,
        sparse_retriever,
        catalog,
        graph_extractor,
        graph_store,
    )