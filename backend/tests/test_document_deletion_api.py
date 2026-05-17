import importlib
import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from config import get_settings
from models import ChunkMetadata, DocumentRecord
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


def _load_api_main():
    import api.main as api_main

    get_settings.cache_clear()
    return importlib.reload(api_main)


def test_delete_document_api_cleans_target_document_state(tmp_path: Path, monkeypatch) -> None:
    api_main = _load_api_main()
    settings = get_settings()
    object.__setattr__(settings, "knowledge_bases_store_path", tmp_path / "knowledge_bases.json")
    object.__setattr__(settings, "documents_store_path", tmp_path / "documents.json")
    object.__setattr__(settings, "chunks_store_path", tmp_path / "chunks.jsonl")
    object.__setattr__(settings, "graph_store_path", tmp_path / "knowledge_graph.db")

    catalog = MetadataCatalog(settings)
    sparse = SparseRetriever(settings)
    graph_store = GraphStore(settings)
    graph_extractor = GraphExtractor()
    dense = InMemoryDenseRetriever()
    service = IngestionService(
        settings=settings,
        chunker=object(),
        dense_retriever=dense,
        sparse_retriever=sparse,
        catalog=catalog,
        graph_extractor=graph_extractor,
        graph_store=graph_store,
    )
    monkeypatch.setattr(api_main, "ingestion_service", service)

    catalog.create_kb("finance", "Finance")
    catalog.upsert_document(
        DocumentRecord(
            document_id="finance-doc-a",
            kb_id="finance",
            kb_name="Finance",
            filename="finance-a.md",
            chunk_count=1,
            created_at="2026-05-10T00:00:00+00:00",
        )
    )
    catalog.upsert_document(
        DocumentRecord(
            document_id="finance-doc-b",
            kb_id="finance",
            kb_name="Finance",
            filename="finance-b.md",
            chunk_count=1,
            created_at="2026-05-10T00:00:00+00:00",
        )
    )

    finance_chunk_a = ChunkMetadata(
        chunk_id="finance-a-1",
        kb_id="finance",
        kb_name="Finance",
        document_id="finance-doc-a",
        source="kb:finance/document:finance-doc-a",
        filename="finance-a.md",
        page=1,
        section="Overview",
        text="FastAPI uses Qdrant for retrieval.",
        token_count=6,
    )
    finance_chunk_b = ChunkMetadata(
        chunk_id="finance-b-1",
        kb_id="finance",
        kb_name="Finance",
        document_id="finance-doc-b",
        source="kb:finance/document:finance-doc-b",
        filename="finance-b.md",
        page=1,
        section="Overview",
        text="Azure OpenAI connects to Finance Service.",
        token_count=6,
    )

    sparse.upsert([finance_chunk_a, finance_chunk_b])
    dense.upsert([finance_chunk_a, finance_chunk_b])
    for chunk in (finance_chunk_a, finance_chunk_b):
        entities, relations = graph_extractor.extract(chunk)
        graph_store.replace_chunk(chunk, entities, relations)

    client = TestClient(api_main.app)
    response = client.delete("/kb/finance/documents/finance-doc-a")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers.get("X-Request-ID")

    assert json.loads(settings.knowledge_bases_store_path.read_text(encoding="utf-8")) == {
        "finance": "Finance"
    }
    remaining_documents = json.loads(settings.documents_store_path.read_text(encoding="utf-8"))
    assert [item["document_id"] for item in remaining_documents] == ["finance-doc-b"]

    persisted_chunks = settings.chunks_store_path.read_text(encoding="utf-8")
    assert '"document_id":"finance-doc-a"' not in persisted_chunks
    assert '"document_id":"finance-doc-b"' in persisted_chunks
    assert [chunk.document_id for chunk in dense.chunks_by_kb["finance"]] == ["finance-doc-b"]

    with sqlite3.connect(settings.graph_store_path) as connection:
        deleted_entities = connection.execute(
            "SELECT COUNT(*) FROM entity_mentions WHERE kb_id = ? AND document_id = ?",
            ("finance", "finance-doc-a"),
        ).fetchone()[0]
        deleted_relations = connection.execute(
            "SELECT COUNT(*) FROM relation_mentions WHERE kb_id = ? AND document_id = ?",
            ("finance", "finance-doc-a"),
        ).fetchone()[0]
        remaining_entities = connection.execute(
            "SELECT COUNT(*) FROM entity_mentions WHERE kb_id = ? AND document_id = ?",
            ("finance", "finance-doc-b"),
        ).fetchone()[0]
        remaining_relations = connection.execute(
            "SELECT COUNT(*) FROM relation_mentions WHERE kb_id = ? AND document_id = ?",
            ("finance", "finance-doc-b"),
        ).fetchone()[0]

    assert deleted_entities == 0
    assert deleted_relations == 0
    assert remaining_entities > 0
    assert remaining_relations > 0