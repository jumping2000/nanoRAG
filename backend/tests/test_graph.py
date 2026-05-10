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