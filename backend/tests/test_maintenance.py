from pathlib import Path
from types import SimpleNamespace

from config import get_settings
from maintenance import purge_orphan_qdrant_points, rebuild_kb_from_sparse_chunks, reset_all_state
from models import ChunkMetadata, DocumentRecord
from qdrant_client.http import models
from rag.catalog import MetadataCatalog
from retrieval.sparse_search import SparseRetriever


class StubDeleteCollectionClient:
    def __init__(self) -> None:
        self.deleted_collections: list[str] = []

    def get_collection(self, collection_name: str) -> dict[str, str]:
        return {"collection_name": collection_name}

    def delete_collection(self, collection_name: str) -> None:
        self.deleted_collections.append(collection_name)


class StubOrphanQdrantClient:
    def __init__(self) -> None:
        self.deleted_selector = None

    def get_collection(self, collection_name: str) -> dict[str, str]:
        return {"collection_name": collection_name}

    def scroll(self, **kwargs):
        if kwargs.get("offset") is None:
            return (
                [
                    SimpleNamespace(id="valid-1", payload={"kb_id": "test2"}),
                    SimpleNamespace(id="orphan-1", payload={}),
                    SimpleNamespace(id="orphan-2", payload=None),
                ],
                "page-2",
            )
        return (
            [
                SimpleNamespace(id="orphan-3", payload={"kb_id": ""}),
                SimpleNamespace(id="valid-2", payload={"kb_id": "finance"}),
            ],
            None,
        )

    def delete(self, *, collection_name: str, points_selector, wait: bool) -> None:
        self.deleted_selector = points_selector


def test_rebuild_kb_from_sparse_chunks_restores_catalog_metadata(tmp_path: Path) -> None:
    settings = get_settings()
    object.__setattr__(settings, "knowledge_bases_store_path", tmp_path / "knowledge_bases.json")
    object.__setattr__(settings, "documents_store_path", tmp_path / "documents.json")
    object.__setattr__(settings, "chunks_store_path", tmp_path / "chunks.jsonl")

    catalog = MetadataCatalog(settings)
    catalog.create_kb("legacy", "Legacy")
    catalog.upsert_document(
        DocumentRecord(
            document_id="legacy-doc",
            kb_id="legacy",
            kb_name="Legacy",
            filename="legacy.pdf",
            chunk_count=1,
            created_at="2026-05-10T00:00:00+00:00",
        )
    )

    sparse = SparseRetriever(settings)
    sparse.upsert(
        [
            ChunkMetadata(
                chunk_id="test2-a",
                kb_id="test2",
                kb_name="Restored KB",
                document_id="doc-a",
                source="kb:test2/document:doc-a",
                filename="soa-a.pdf",
                page=1,
                section="Overview",
                text="soa backplane architecture",
                token_count=4,
            ),
            ChunkMetadata(
                chunk_id="test2-b",
                kb_id="test2",
                kb_name="Restored KB",
                document_id="doc-a",
                source="kb:test2/document:doc-a",
                filename="soa-a.pdf",
                page=2,
                section="Details",
                text="soa services and contracts",
                token_count=5,
            ),
            ChunkMetadata(
                chunk_id="test2-c",
                kb_id="test2",
                kb_name="Restored KB",
                document_id="doc-b",
                source="kb:test2/document:doc-b",
                filename="soa-b.pdf",
                page=1,
                section="Overview",
                text="integration flows",
                token_count=2,
            ),
        ]
    )

    summary = rebuild_kb_from_sparse_chunks(settings, "test2")

    rebuilt_catalog = MetadataCatalog(settings)
    rebuilt_kb = rebuilt_catalog.get_kb("test2")
    rebuilt_documents = rebuilt_catalog.list_documents("test2")

    assert summary.kb_id == "test2"
    assert summary.kb_name == "Restored KB"
    assert summary.documents == 2
    assert summary.chunks == 3
    assert rebuilt_kb.documents == 2
    assert rebuilt_kb.chunks == 3
    assert [document.document_id for document in rebuilt_documents] == ["doc-a", "doc-b"]
    assert [document.chunk_count for document in rebuilt_documents] == [2, 1]
    assert rebuilt_catalog.get_kb("legacy").documents == 1


def test_purge_orphan_qdrant_points_deletes_only_missing_kb_id_entries() -> None:
    settings = get_settings()
    client = StubOrphanQdrantClient()

    deleted = purge_orphan_qdrant_points(settings, client=client)

    assert deleted == 3
    assert isinstance(client.deleted_selector, models.PointIdsList)
    assert client.deleted_selector.points == ["orphan-1", "orphan-2", "orphan-3"]


def test_reset_all_state_clears_local_files_and_qdrant_collection(tmp_path: Path) -> None:
    settings = get_settings()
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    (uploads_dir / "doc.pdf").write_text("pdf", encoding="utf-8")

    object.__setattr__(settings, "knowledge_bases_store_path", tmp_path / "knowledge_bases.json")
    object.__setattr__(settings, "documents_store_path", tmp_path / "documents.json")
    object.__setattr__(settings, "chunks_store_path", tmp_path / "chunks.jsonl")
    object.__setattr__(settings, "graph_store_path", tmp_path / "knowledge_graph.db")
    object.__setattr__(settings, "uploads_dir", uploads_dir)

    settings.knowledge_bases_store_path.write_text('{"test":"test"}', encoding="utf-8")
    settings.documents_store_path.write_text('[{"document_id":"doc","kb_id":"test","kb_name":"test","filename":"doc.pdf","chunk_count":1,"created_at":"2026-05-10T00:00:00+00:00"}]', encoding="utf-8")
    settings.chunks_store_path.write_text('{"chunk_id":"chunk-1","kb_id":"test","kb_name":"test","document_id":"doc","source":"kb:test/document:doc","filename":"doc.pdf","page":1,"section":"Overview","text":"hello","token_count":1}', encoding="utf-8")
    settings.graph_store_path.write_text("sqlite", encoding="utf-8")

    client = StubDeleteCollectionClient()

    summary = reset_all_state(settings, client=client)

    assert settings.knowledge_bases_store_path.read_text(encoding="utf-8") == "{}"
    assert settings.documents_store_path.read_text(encoding="utf-8") == "[]"
    assert settings.chunks_store_path.read_text(encoding="utf-8") == ""
    assert list(settings.uploads_dir.iterdir()) == []
    assert not settings.graph_store_path.exists()
    assert summary.uploads_deleted == 1
    assert summary.qdrant_collection_deleted is True
    assert client.deleted_collections == [settings.qdrant_collection]