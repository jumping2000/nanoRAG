from pathlib import Path

from config import get_settings
from models import ChunkMetadata, DocumentRecord
from rag.catalog import MetadataCatalog
from retrieval.sparse_search import SparseRetriever


def test_catalog_tracks_kb_and_documents(tmp_path: Path) -> None:
    settings = get_settings()
    object.__setattr__(settings, "knowledge_bases_store_path", tmp_path / "knowledge_bases.json")
    object.__setattr__(settings, "documents_store_path", tmp_path / "documents.json")

    catalog = MetadataCatalog(settings)
    catalog.create_kb("finance", "Finance")
    catalog.upsert_document(
        DocumentRecord(
            document_id="finance-report-123",
            kb_id="finance",
            kb_name="Finance",
            filename="report.pdf",
            chunk_count=3,
            created_at="2026-05-10T00:00:00+00:00",
        ),
    )

    kb = catalog.get_kb("finance")

    assert kb.documents == 1
    assert kb.chunks == 3
    assert catalog.list_documents("finance")[0].document_id == "finance-report-123"


def test_sparse_retriever_isolates_results_by_kb(tmp_path: Path) -> None:
    settings = get_settings()
    object.__setattr__(settings, "chunks_store_path", tmp_path / "chunks.jsonl")

    retriever = SparseRetriever(settings)
    retriever.upsert(
        [
            ChunkMetadata(
                chunk_id="finance-1",
                kb_id="finance",
                kb_name="Finance",
                document_id="finance-doc",
                source="kb:finance/document:finance-doc",
                filename="finance.md",
                page=1,
                section="Overview",
                text="capital ratio and stress testing overview",
                token_count=6,
            ),
            ChunkMetadata(
                chunk_id="legal-1",
                kb_id="legal",
                kb_name="Legal",
                document_id="legal-doc",
                source="kb:legal/document:legal-doc",
                filename="legal.md",
                page=1,
                section="Overview",
                text="contract clauses and liabilities overview",
                token_count=6,
            ),
        ],
    )

    finance_results = retriever.search("capital ratio", kb_id="finance", top_k=5)
    legal_results = retriever.search("capital ratio", kb_id="legal", top_k=5)

    assert [item.kb_id for item in finance_results] == ["finance"]
    assert legal_results == []