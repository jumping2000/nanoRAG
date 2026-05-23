"""Tests for the nanoRAG MCP server — structure and tool contract coverage."""

from __future__ import annotations

import importlib

from config import get_settings


def _load_mcp_server_module(monkeypatch) -> object:
    monkeypatch.setattr("bootstrap.build_ingestion_runtime", lambda s: _fake_runtime())
    get_settings.cache_clear()
    import mcp_server

    return importlib.reload(mcp_server)


class _FakeDenseRetriever:
    def upsert(self, chunks):
        pass

    def delete_document(self, kb_id, document_id):
        pass

    def delete_kb(self, kb_id):
        pass

    def search(self, query, kb_id, top_k):
        return []


class _FakeSparseRetriever:
    def upsert(self, chunks):
        pass

    def delete_document(self, kb_id, document_id):
        pass

    def delete_kb(self, kb_id):
        pass

    def total_chunks(self, kb_id=None):
        return 0

    def search(self, query, kb_id, top_k):
        return []


class _FakeCatalog:
    def create_kb(self, kb_id, name):
        pass

    def get_kb(self, kb_id):

        class KB:
            id = kb_id
            name = kb_id

        return KB()

    def list_kbs(self):
        return []

    def list_documents(self, kb_id):
        return []


class _FakeGraphStore:
    def get_snapshot(self, kb_id, limit=18, min_weight=1):
        from models import GraphSnapshot, GraphStats

        return GraphSnapshot(kb_id=kb_id, nodes=[], edges=[], stats=GraphStats())

    def get_node_detail(self, kb_id, entity_id, evidence_limit=12):
        raise LookupError(f"Graph node not found: {entity_id}")

    def delete_document(self, kb_id, document_id):
        pass


class _FakeIngestionService:
    def indexed_chunks(self):
        return 0

    def list_documents(self, kb_id):
        return []

    def delete_document(self, kb_id, document_id):
        pass


def _fake_runtime():
    return type(
        "FakeRuntime",
        (),
        {
            "dense_retriever": _FakeDenseRetriever(),
            "sparse_retriever": _FakeSparseRetriever(),
            "catalog": _FakeCatalog(),
            "graph_store": _FakeGraphStore(),
            "ingestion_service": _FakeIngestionService(),
            "chunker": object(),
            "embedding_provider": object(),
            "graph_extractor": object(),
        },
    )()


def test_mcp_server_module_exposes_all_eight_tools(monkeypatch) -> None:
    mcp_mod = _load_mcp_server_module(monkeypatch)
    assert hasattr(mcp_mod, "mcp")
    tool_names = {tool.name for tool in mcp_mod.mcp._tool_manager._tools.values()}
    expected = {
        "nanorag_health",
        "nanorag_list_kbs",
        "nanorag_list_documents",
        "nanorag_get_graph",
        "nanorag_get_node_detail",
        "nanorag_chat",
        "nanorag_upload_document",
        "nanorag_delete_document",
    }
    assert tool_names == expected


def test_nanorag_health_returns_expected_keys(monkeypatch) -> None:
    mcp_mod = _load_mcp_server_module(monkeypatch)
    health = mcp_mod.nanorag_health()
    assert health["status"] == "ok"
    assert "llm_provider" in health
    assert "embedding_provider" in health
    assert health["indexed_chunks"] == 0


def test_nanorag_list_kbs_returns_list(monkeypatch) -> None:
    mcp_mod = _load_mcp_server_module(monkeypatch)
    kb_list = mcp_mod.nanorag_list_kbs()
    assert isinstance(kb_list, list)


def test_nanorag_list_documents_returns_list(monkeypatch) -> None:
    mcp_mod = _load_mcp_server_module(monkeypatch)
    docs = mcp_mod.nanorag_list_documents(kb_id="finance")
    assert isinstance(docs, list)


def test_nanorag_get_graph_returns_empty_snapshot(monkeypatch) -> None:
    mcp_mod = _load_mcp_server_module(monkeypatch)
    snapshot = mcp_mod.nanorag_get_graph(kb_id="finance")
    assert snapshot["kb_id"] == "finance"
    assert snapshot["nodes"] == []
    assert snapshot["edges"] == []
    assert snapshot["stats"]["nodes"] == 0


def test_nanorag_get_node_detail_returns_error_for_unknown_entity(monkeypatch) -> None:
    mcp_mod = _load_mcp_server_module(monkeypatch)
    result = mcp_mod.nanorag_get_node_detail(kb_id="finance", entity_id="unknown")
    assert "error" in result


def test_nanorag_chat_returns_no_context_when_chunks_empty(monkeypatch) -> None:
    mcp_mod = _load_mcp_server_module(monkeypatch)

    def fake_plan(message):
        from agents.orchestrator import RetrievalPlan

        return RetrievalPlan(
            original_query=message,
            search_query=message,
            needs_retrieval=True,
            answer_style="grounded",
        )

    monkeypatch.setattr(mcp_mod.orchestrator, "plan", fake_plan)
    monkeypatch.setattr(mcp_mod.hybrid_retriever, "search", lambda *a, **kw: [])

    result = mcp_mod.nanorag_chat(kb_id="finance", message="capital ratio", top_k=3)
    assert "answer" in result
    assert result["sources"] == []
    assert result["search_query"] == "capital ratio"


def test_nanorag_delete_document_returns_ok(monkeypatch) -> None:
    mcp_mod = _load_mcp_server_module(monkeypatch)
    result = mcp_mod.nanorag_delete_document(kb_id="finance", document_id="doc-1")
    assert result["status"] == "ok"
