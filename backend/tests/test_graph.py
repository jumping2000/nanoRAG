from pathlib import Path

from config import get_settings
from models import ChunkMetadata
from rag.graph_extractor import GraphExtractor
from rag.graph_store import GraphStore


def test_graph_snapshot_extracts_and_aggregates_relations(tmp_path: Path) -> None:
    settings = get_settings()
    object.__setattr__(settings, "graph_store_path", tmp_path / "knowledge_graph.db")

    extractor = GraphExtractor()
    store = GraphStore(settings)
    chunk = ChunkMetadata(
        chunk_id="arch-1",
        kb_id="architecture",
        kb_name="Architecture",
        document_id="architecture-doc",
        source="kb:architecture/document:architecture-doc",
        filename="architecture.md",
        page=1,
        section="Overview",
        text="FastAPI uses Qdrant for vector retrieval. Qdrant stores embeddings for FastAPI services.",
        token_count=14,
    )

    entities, relations = extractor.extract(chunk)
    store.replace_chunk(chunk, entities, relations)
    snapshot = store.get_snapshot("architecture")

    assert {node.label for node in snapshot.nodes} >= {"FastAPI", "Qdrant"}
    assert any(edge.predicate == "uses" for edge in snapshot.edges)
    assert snapshot.stats.nodes >= 2
    assert snapshot.stats.edges >= 1


def test_graph_store_isolates_and_deletes_by_kb_and_document(tmp_path: Path) -> None:
    settings = get_settings()
    object.__setattr__(settings, "graph_store_path", tmp_path / "knowledge_graph.db")

    extractor = GraphExtractor()
    store = GraphStore(settings)
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

    for chunk in (finance_chunk, legal_chunk):
        entities, relations = extractor.extract(chunk)
        store.replace_chunk(chunk, entities, relations)

    finance_snapshot = store.get_snapshot("finance")
    legal_snapshot = store.get_snapshot("legal")

    assert {node.label for node in finance_snapshot.nodes} >= {"FastAPI", "Qdrant"}
    assert {node.label for node in legal_snapshot.nodes} >= {"OpenAI", "Azure"}

    store.delete_document("finance", "finance-doc")

    assert store.get_snapshot("finance").stats.nodes == 0
    assert store.get_snapshot("legal").stats.nodes >= 2


def test_graph_node_detail_aggregates_documents_relations_and_kb_isolation(tmp_path: Path) -> None:
    settings = get_settings()
    object.__setattr__(settings, "graph_store_path", tmp_path / "knowledge_graph.db")

    extractor = GraphExtractor()
    store = GraphStore(settings)
    finance_chunk_a = ChunkMetadata(
        chunk_id="finance-1",
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
        chunk_id="finance-2",
        kb_id="finance",
        kb_name="Finance",
        document_id="finance-doc-a",
        source="kb:finance/document:finance-doc-a",
        filename="finance-a.md",
        page=2,
        section="Architecture",
        text="FastAPI uses Qdrant for vector indexing.",
        token_count=6,
    )
    finance_chunk_c = ChunkMetadata(
        chunk_id="finance-3",
        kb_id="finance",
        kb_name="Finance",
        document_id="finance-doc-b",
        source="kb:finance/document:finance-doc-b",
        filename="finance-b.md",
        page=1,
        section="Hosting",
        text="FastAPI runs on Azure.",
        token_count=4,
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
        text="FastAPI references Contracts.",
        token_count=3,
    )

    for chunk in (finance_chunk_a, finance_chunk_b, finance_chunk_c, legal_chunk):
        entities, relations = extractor.extract(chunk)
        store.replace_chunk(chunk, entities, relations)

    detail = store.get_node_detail("finance", "fastapi")

    assert detail.node.label == "FastAPI"
    assert detail.stats == {"mentions": 3, "documents": 2, "relations": 2}
    assert [(document.document_id, document.mention_count) for document in detail.documents] == [
        ("finance-doc-a", 2),
        ("finance-doc-b", 1),
    ]
    assert [(relation.predicate, relation.counterpart.label, relation.weight) for relation in detail.relations] == [
        ("uses", "Qdrant", 2),
        ("runs_on", "Azure", 1),
    ]


def test_graph_node_detail_updates_after_document_delete(tmp_path: Path) -> None:
    settings = get_settings()
    object.__setattr__(settings, "graph_store_path", tmp_path / "knowledge_graph.db")

    extractor = GraphExtractor()
    store = GraphStore(settings)
    chunk_a = ChunkMetadata(
        chunk_id="finance-1",
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
    chunk_b = ChunkMetadata(
        chunk_id="finance-2",
        kb_id="finance",
        kb_name="Finance",
        document_id="finance-doc-b",
        source="kb:finance/document:finance-doc-b",
        filename="finance-b.md",
        page=1,
        section="Hosting",
        text="FastAPI runs on Azure.",
        token_count=4,
    )

    for chunk in (chunk_a, chunk_b):
        entities, relations = extractor.extract(chunk)
        store.replace_chunk(chunk, entities, relations)

    store.delete_document("finance", "finance-doc-b")
    detail = store.get_node_detail("finance", "fastapi")

    assert detail.stats == {"mentions": 1, "documents": 1, "relations": 1}
    assert [document.document_id for document in detail.documents] == ["finance-doc-a"]
    assert [(relation.predicate, relation.counterpart.label) for relation in detail.relations] == [
        ("uses", "Qdrant"),
    ]