from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile

from chunking.structural_chunker import StructuralChunker
from config import get_settings
from rag.catalog import MetadataCatalog
from rag.graph_store import GraphStore
from rag.ingest import IngestionService
from tests.graph_test_support import InMemoryDenseRetriever
from rag.graph_extractor import GraphExtractor
from retrieval.sparse_search import SparseRetriever


class BackgroundTaskRecorder:
    def __init__(self) -> None:
        self.tasks: list[tuple[object, tuple[object, ...], dict[str, object]]] = []

    def add_task(self, func, *args, **kwargs) -> None:
        self.tasks.append((func, args, kwargs))


@pytest.mark.asyncio
async def test_upload_persists_document_before_background_graph_extraction(tmp_path: Path) -> None:
    settings = get_settings()
    object.__setattr__(settings, "knowledge_bases_store_path", tmp_path / "knowledge_bases.json")
    object.__setattr__(settings, "documents_store_path", tmp_path / "documents.json")
    object.__setattr__(settings, "chunks_store_path", tmp_path / "chunks.jsonl")
    object.__setattr__(settings, "graph_store_path", tmp_path / "knowledge_graph.db")
    object.__setattr__(settings, "graph_extraction_enabled", True)

    catalog = MetadataCatalog(settings)
    dense = InMemoryDenseRetriever()
    sparse = SparseRetriever(settings)
    graph_store = GraphStore(settings)
    service = IngestionService(
        settings=settings,
        chunker=StructuralChunker(max_tokens=80, overlap_tokens=10),
        dense_retriever=dense,
        sparse_retriever=sparse,
        catalog=catalog,
        graph_extractor=GraphExtractor(),
        graph_store=graph_store,
    )
    tasks = BackgroundTaskRecorder()

    catalog.create_kb("architecture", "Architecture")
    upload = UploadFile(
        filename="architecture.md",
        file=BytesIO(b"# Overview\n\nFastAPI uses Qdrant for vector retrieval.\n"),
    )

    response = await service._ingest_upload("architecture", upload, background_tasks=tasks)

    assert response.filename == "architecture.md"
    assert response.ingested_chunks == 1
    assert len(tasks.tasks) == 1
    assert [document.filename for document in catalog.list_documents("architecture")] == ["architecture.md"]
    assert sparse.total_chunks("architecture") == 1
    assert len(dense.chunks_by_kb["architecture"]) == 1
    assert graph_store.get_snapshot("architecture").stats.nodes == 0