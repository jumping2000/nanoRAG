from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from chunking.structural_chunker import StructuralChunker
from config import Settings, get_settings
from models import ChunkMetadata
from rag.catalog import MetadataCatalog
from rag.graph_extractor import GraphExtractor
from rag.graph_store import GraphStore
from rag.ingest import IngestionService
from retrieval.sparse_search import SparseRetriever


class InMemoryDenseRetriever:
    def __init__(self) -> None:
        self.chunks_by_kb: dict[str, list[ChunkMetadata]] = {}

    def upsert(self, chunks: list[ChunkMetadata]) -> None:
        for chunk in chunks:
            self.chunks_by_kb.setdefault(chunk.kb_id, []).append(chunk)

    def delete_document(self, kb_id: str, document_id: str) -> None:
        remaining = [
            chunk for chunk in self.chunks_by_kb.get(kb_id, []) if chunk.document_id != document_id
        ]
        if remaining:
            self.chunks_by_kb[kb_id] = remaining
            return
        self.chunks_by_kb.pop(kb_id, None)

    def delete_kb(self, kb_id: str) -> None:
        self.chunks_by_kb.pop(kb_id, None)


@dataclass(slots=True)
class GraphTestRuntime:
    api_main: ModuleType
    settings: Settings
    chunker: StructuralChunker
    catalog: MetadataCatalog
    dense_retriever: InMemoryDenseRetriever
    sparse_retriever: SparseRetriever
    graph_store: GraphStore
    graph_extractor: GraphExtractor
    ingestion_service: IngestionService


def load_api_main() -> ModuleType:
    import api.main as api_main

    get_settings.cache_clear()
    return importlib.reload(api_main)


def setup_test_runtime(tmp_path: Path, monkeypatch: Any) -> GraphTestRuntime:
    api_main = load_api_main()
    settings = get_settings()
    object.__setattr__(settings, "knowledge_bases_store_path", tmp_path / "knowledge_bases.json")
    object.__setattr__(settings, "documents_store_path", tmp_path / "documents.json")
    object.__setattr__(settings, "chunks_store_path", tmp_path / "chunks.jsonl")
    object.__setattr__(settings, "graph_store_path", tmp_path / "knowledge_graph.db")

    chunker = StructuralChunker(
        max_tokens=settings.chunk_size_tokens,
        overlap_tokens=settings.chunk_overlap_tokens,
    )
    catalog = MetadataCatalog(settings)
    dense_retriever = InMemoryDenseRetriever()
    sparse_retriever = SparseRetriever(settings)
    graph_store = GraphStore(settings)
    graph_extractor = GraphExtractor()
    ingestion_service = IngestionService(
        settings=settings,
        chunker=chunker,
        dense_retriever=dense_retriever,
        sparse_retriever=sparse_retriever,
        catalog=catalog,
        graph_extractor=graph_extractor,
        graph_store=graph_store,
    )

    monkeypatch.setattr(api_main, "settings", settings)
    monkeypatch.setattr(api_main, "catalog", catalog)
    monkeypatch.setattr(api_main, "dense_retriever", dense_retriever)
    monkeypatch.setattr(api_main, "sparse_retriever", sparse_retriever)
    monkeypatch.setattr(api_main, "graph_store", graph_store)
    monkeypatch.setattr(api_main, "ingestion_service", ingestion_service)

    return GraphTestRuntime(
        api_main=api_main,
        settings=settings,
        chunker=chunker,
        catalog=catalog,
        dense_retriever=dense_retriever,
        sparse_retriever=sparse_retriever,
        graph_store=graph_store,
        graph_extractor=graph_extractor,
        ingestion_service=ingestion_service,
    )