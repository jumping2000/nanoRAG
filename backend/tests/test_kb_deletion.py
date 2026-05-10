import json
import sqlite3
from pathlib import Path

from fastapi import HTTPException

from config import get_settings
from models import ChunkMetadata, DocumentRecord
from rag.catalog import MetadataCatalog
from rag.graph_extractor import GraphExtractor
from rag.graph_store import GraphStore
from rag.ingest import IngestionService
from retrieval.sparse_search import SparseRetriever


class StubCatalog:
    def __init__(self, existing_kbs: set[str] | None = None) -> None:
        self.existing_kbs = set(existing_kbs or set())
        self.deleted_calls: list[str] = []

    def delete_kb(self, kb_id: str) -> bool:
        self.deleted_calls.append(kb_id)
        existed = kb_id in self.existing_kbs
        self.existing_kbs.discard(kb_id)
        return existed


class StubDeleter:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.deleted_calls: list[str] = []

    def delete_kb(self, kb_id: str) -> None:
        self.deleted_calls.append(kb_id)
        if self.should_fail:
            raise RuntimeError(f"{kb_id} delete failed")


class InMemoryDenseRetriever:
    def __init__(self) -> None:
        self.chunks_by_kb: dict[str, list[ChunkMetadata]] = {}

    def upsert(self, chunks: list[ChunkMetadata]) -> None:
        for chunk in chunks:
            self.chunks_by_kb.setdefault(chunk.kb_id, []).append(chunk)

    def delete_kb(self, kb_id: str) -> None:
        self.chunks_by_kb.pop(kb_id, None)


def _service(catalog: StubCatalog, dense: StubDeleter, sparse: StubDeleter, graph: StubDeleter) -> IngestionService:
    return IngestionService(
        settings=object(),
        chunker=object(),
        dense_retriever=dense,
        sparse_retriever=sparse,
        catalog=catalog,
        graph_extractor=object(),
        graph_store=graph,
    )


def test_delete_kb_is_idempotent_and_reports_store_statuses() -> None:
    catalog = StubCatalog(existing_kbs={"finance"})
    dense = StubDeleter()
    sparse = StubDeleter()
    graph = StubDeleter()
    service = _service(catalog, dense, sparse, graph)

    first_result = service.delete_kb("finance")
    second_result = service.delete_kb("finance")

    assert first_result.status == "ok"
    assert [item.status for item in first_result.stores] == ["deleted", "deleted", "deleted", "deleted"]
    assert second_result.status == "ok"
    assert second_result.stores[0].store == "metadata"
    assert second_result.stores[0].status == "already_absent"
    assert dense.deleted_calls == ["finance", "finance"]
    assert sparse.deleted_calls == ["finance", "finance"]
    assert graph.deleted_calls == ["finance", "finance"]


def test_delete_kb_reports_partial_failure_after_continuing_other_stores() -> None:
    catalog = StubCatalog(existing_kbs={"finance"})
    dense = StubDeleter(should_fail=True)
    sparse = StubDeleter()
    graph = StubDeleter()
    service = _service(catalog, dense, sparse, graph)

    try:
        service.delete_kb("finance")
        raise AssertionError("Expected HTTPException")
    except HTTPException as error:
        assert error.status_code == 500
        assert isinstance(error.detail, dict)
        detail = error.detail
        assert detail["kb_id"] == "finance"
        assert [item["store"] for item in detail["stores"]] == ["metadata", "qdrant", "sparse", "graph"]
        assert detail["stores"][1]["status"] == "failed"
        assert detail["stores"][2]["status"] == "deleted"
        assert detail["stores"][3]["status"] == "deleted"

    assert sparse.deleted_calls == ["finance"]
    assert graph.deleted_calls == ["finance"]


def test_delete_kb_cleans_local_metadata_sparse_graph_and_dense_state(tmp_path: Path) -> None:
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

    catalog.create_kb("finance", "Finance")
    catalog.create_kb("legal", "Legal")
    catalog.upsert_document(
        DocumentRecord(
            document_id="finance-doc",
            kb_id="finance",
            kb_name="Finance",
            filename="finance.md",
            chunk_count=1,
            created_at="2026-05-10T00:00:00+00:00",
        )
    )
    catalog.upsert_document(
        DocumentRecord(
            document_id="legal-doc",
            kb_id="legal",
            kb_name="Legal",
            filename="legal.md",
            chunk_count=1,
            created_at="2026-05-10T00:00:00+00:00",
        )
    )

    finance_chunk = ChunkMetadata(
        chunk_id="finance-1",
        kb_id="finance",
        kb_name="Finance",
        document_id="finance-doc",
        source="kb:finance/document:finance-doc",
        filename="finance.md",
        page=1,
        section="Overview",
        text="FastAPI uses Qdrant for retrieval.",
        token_count=6,
    )
    legal_chunk = ChunkMetadata(
        chunk_id="legal-1",
        kb_id="legal",
        kb_name="Legal",
        document_id="legal-doc",
        source="kb:legal/document:legal-doc",
        filename="legal.md",
        page=1,
        section="Overview",
        text="OpenAI uses Azure for hosting.",
        token_count=5,
    )

    sparse.upsert([finance_chunk, legal_chunk])
    dense.upsert([finance_chunk, legal_chunk])
    for chunk in (finance_chunk, legal_chunk):
        entities, relations = graph_extractor.extract(chunk)
        graph_store.replace_chunk(chunk, entities, relations)

    result = service.delete_kb("finance")

    assert result.status == "ok"
    assert "finance" not in json.loads(settings.knowledge_bases_store_path.read_text(encoding="utf-8"))
    remaining_documents = json.loads(settings.documents_store_path.read_text(encoding="utf-8"))
    assert [item["kb_id"] for item in remaining_documents] == ["legal"]
    persisted_chunks = settings.chunks_store_path.read_text(encoding="utf-8")
    assert '"kb_id":"finance"' not in persisted_chunks
    assert '"kb_id":"legal"' in persisted_chunks
    assert "finance" not in dense.chunks_by_kb
    assert "legal" in dense.chunks_by_kb

    with sqlite3.connect(settings.graph_store_path) as connection:
        finance_entities = connection.execute(
            "SELECT COUNT(*) FROM entity_mentions WHERE kb_id = ?",
            ("finance",),
        ).fetchone()[0]
        finance_relations = connection.execute(
            "SELECT COUNT(*) FROM relation_mentions WHERE kb_id = ?",
            ("finance",),
        ).fetchone()[0]
        legal_entities = connection.execute(
            "SELECT COUNT(*) FROM entity_mentions WHERE kb_id = ?",
            ("legal",),
        ).fetchone()[0]

    assert finance_entities == 0
    assert finance_relations == 0
    assert legal_entities > 0