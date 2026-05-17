from pathlib import Path

import pytest

from config import get_settings
from models import ChunkMetadata, DocumentRecord
from rag.catalog import MetadataCatalog
from retrieval.sparse_search import SparseRetriever


@pytest.mark.parametrize(
    ("raw_env", "expected", "deep_observability", "trace_details"),
    [
        ("development", "development", True, False),
        ("production", "production", False, False),
        ("debug", "debug", True, True),
        (" DEBUG ", "debug", True, True),
    ],
)
def test_settings_normalize_supported_app_env_values(
    monkeypatch: pytest.MonkeyPatch,
    raw_env: str,
    expected: str,
    deep_observability: bool,
    trace_details: bool,
) -> None:
    monkeypatch.setenv("APP_ENV", raw_env)

    settings = get_settings()

    assert settings.environment == expected
    assert settings.enable_deep_observability is deep_observability
    assert settings.enable_trace_details is trace_details


def test_settings_reject_invalid_app_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")

    with pytest.raises(ValueError, match="APP_ENV must be one of"):
        get_settings()


def test_graph_extraction_settings_apply_explicit_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRAPH_EXTRACTION_ENABLED", "true")
    monkeypatch.setenv("GRAPH_EXTRACTION_PROVIDER", "ollama")
    monkeypatch.setenv("GRAPH_EXTRACTION_API_KEY", "graph-key")
    monkeypatch.setenv("GRAPH_EXTRACTION_BASE_URL", "https://graph.example/v1")
    monkeypatch.setenv("GRAPH_EXTRACTION_MODEL", "graph-model")
    monkeypatch.setenv("GRAPH_EXTRACTION_MAX_CHUNKS_PER_DOCUMENT", "12")
    monkeypatch.setenv("GRAPH_EXTRACTION_MIN_CONFIDENCE", "0.7")

    settings = get_settings()

    assert settings.graph_extraction_enabled is True
    assert settings.graph_extraction_provider == "ollama"
    assert settings.graph_extraction_api_key == "graph-key"
    assert settings.graph_extraction_base_url == "https://graph.example/v1"
    assert settings.graph_extraction_model == "graph-model"
    assert settings.graph_extraction_max_chunks_per_document == 12
    assert settings.graph_extraction_min_confidence == 0.7


def test_graph_extraction_settings_reuse_llm_credentials_when_provider_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("LLM_API_KEY", "llm-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://router.example/v1")
    monkeypatch.setenv("GRAPH_EXTRACTION_PROVIDER", "openrouter")
    monkeypatch.setenv("GRAPH_EXTRACTION_MODEL", "graph-model")

    settings = get_settings()

    assert settings.graph_extraction_provider == "openrouter"
    assert settings.graph_extraction_api_key == "llm-key"
    assert settings.graph_extraction_base_url == "https://router.example/v1"
    assert settings.graph_extraction_model == "graph-model"


def test_graph_extraction_settings_do_not_reuse_llm_credentials_when_provider_differs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_API_KEY", "llm-key")
    monkeypatch.setenv("GRAPH_EXTRACTION_PROVIDER", "openrouter")
    monkeypatch.setenv("GRAPH_EXTRACTION_MODEL", "same-model-name")

    settings = get_settings()

    assert settings.graph_extraction_provider == "openrouter"
    assert settings.graph_extraction_api_key is None
    assert settings.graph_extraction_base_url == "https://openrouter.ai/api/v1"
    assert settings.graph_extraction_model == "same-model-name"


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