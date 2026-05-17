import importlib
import json

from fastapi.testclient import TestClient

from agents.orchestrator import RetrievalPlan
from config import get_settings
from models import RetrievedChunk


def _load_api_main(app_env: str):
    import api.main as api_main

    get_settings.cache_clear()
    return importlib.reload(api_main)


def test_health_headers_follow_app_env(monkeypatch) -> None:
    expectations = {
        "production": {"mode": None, "events": None},
        "development": {"mode": "development", "events": None},
        "debug": {"mode": "debug", "events": "2"},
    }

    for app_env, expected in expectations.items():
        monkeypatch.setenv("APP_ENV", app_env)
        api_main = _load_api_main(app_env)
        client = TestClient(api_main.app)

        response = client.get("/health")

        assert response.status_code == 200
        assert response.headers.get("X-Request-ID")
        assert response.headers.get("X-Debug-Trace-Mode") == expected["mode"]
        assert response.headers.get("X-Debug-Trace-Events") == expected["events"]


def test_chat_stream_emits_debug_trace_event_in_debug_mode(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "debug")
    api_main = _load_api_main("debug")
    client = TestClient(api_main.app)

    chunk = RetrievedChunk(
        chunk_id="finance-1",
        kb_id="finance",
        kb_name="Finance",
        document_id="finance-doc",
        source="kb:finance/document:finance-doc",
        filename="finance.md",
        page=1,
        section="Overview",
        text="capital ratio overview",
        token_count=3,
        score=0.9,
        rank=1,
    )

    monkeypatch.setattr(api_main.catalog, "get_kb", lambda kb_id: object())
    monkeypatch.setattr(
        api_main.orchestrator,
        "plan",
        lambda message: RetrievalPlan(
            original_query=message,
            search_query="capital ratio",
            needs_retrieval=True,
            answer_style="grounded",
        ),
    )
    monkeypatch.setattr(api_main.hybrid_retriever, "search", lambda *args, **kwargs: [chunk])
    monkeypatch.setattr(api_main.knowledge_agent, "stream_answer", lambda *args, **kwargs: iter(["hello"]))

    response = client.post(
        "/chat",
        json={"message": "Show capital ratio", "kb_id": "finance", "top_k": 3},
    )

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")
    assert response.headers.get("X-Debug-Trace-Mode") == "debug"

    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    event_types = [event["type"] for event in events]

    assert event_types == ["meta", "token", "sources", "debug", "done"]
    assert events[3]["trace"]["requestId"] == response.headers["X-Request-ID"]
    assert events[3]["trace"]["environment"] == "debug"
    assert any(item["component"] == "api" for item in events[3]["trace"]["events"])


def test_chat_stream_omits_debug_trace_event_outside_debug(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    api_main = _load_api_main("development")
    client = TestClient(api_main.app)

    chunk = RetrievedChunk(
        chunk_id="finance-1",
        kb_id="finance",
        kb_name="Finance",
        document_id="finance-doc",
        source="kb:finance/document:finance-doc",
        filename="finance.md",
        page=1,
        section="Overview",
        text="capital ratio overview",
        token_count=3,
        score=0.9,
        rank=1,
    )

    monkeypatch.setattr(api_main.catalog, "get_kb", lambda kb_id: object())
    monkeypatch.setattr(
        api_main.orchestrator,
        "plan",
        lambda message: RetrievalPlan(
            original_query=message,
            search_query="capital ratio",
            needs_retrieval=True,
            answer_style="grounded",
        ),
    )
    monkeypatch.setattr(api_main.hybrid_retriever, "search", lambda *args, **kwargs: [chunk])
    monkeypatch.setattr(api_main.knowledge_agent, "stream_answer", lambda *args, **kwargs: iter(["hello"]))

    response = client.post(
        "/chat",
        json={"message": "Show capital ratio", "kb_id": "finance", "top_k": 3},
    )

    assert response.status_code == 200
    assert response.headers.get("X-Debug-Trace-Mode") == "development"
    assert response.headers.get("X-Debug-Trace-Events") is None

    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]

    assert [event["type"] for event in events] == ["meta", "token", "sources", "done"]


def test_chat_stream_uses_graph_reranked_chunk_order_for_answer_and_sources(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    api_main = _load_api_main("development")
    client = TestClient(api_main.app)

    first_chunk = RetrievedChunk(
        chunk_id="finance-1",
        kb_id="finance",
        kb_name="Finance",
        document_id="finance-doc-1",
        source="kb:finance/document:finance-doc-1",
        filename="finance-1.md",
        page=1,
        section="Overview",
        text="capital ratio overview",
        token_count=3,
        score=0.9,
        rank=1,
    )
    second_chunk = RetrievedChunk(
        chunk_id="finance-2",
        kb_id="finance",
        kb_name="Finance",
        document_id="finance-doc-2",
        source="kb:finance/document:finance-doc-2",
        filename="finance-2.md",
        page=2,
        section="Architecture",
        text="capital ratio dependencies",
        token_count=3,
        score=0.89,
        rank=2,
    )

    monkeypatch.setattr(api_main.catalog, "get_kb", lambda kb_id: object())
    monkeypatch.setattr(
        api_main.orchestrator,
        "plan",
        lambda message: RetrievalPlan(
            original_query=message,
            search_query="capital ratio",
            needs_retrieval=True,
            answer_style="grounded",
        ),
    )
    monkeypatch.setattr(
        api_main.hybrid_retriever,
        "search",
        lambda *args, **kwargs: [first_chunk, second_chunk],
    )
    monkeypatch.setattr(
        api_main.graph_reranker,
        "rerank",
        lambda kb_id, chunks: [
            chunks[1].model_copy(update={"score": 0.99, "rank": 1}),
            chunks[0].model_copy(update={"score": 0.95, "rank": 2}),
        ],
    )

    captured_chunk_ids: list[str] = []

    def fake_stream_answer(question, plan, chunks):
        captured_chunk_ids[:] = [chunk.chunk_id for chunk in chunks]
        return iter(["hello"])

    monkeypatch.setattr(api_main.knowledge_agent, "stream_answer", fake_stream_answer)

    response = client.post(
        "/chat",
        json={"message": "Show capital ratio", "kb_id": "finance", "top_k": 3},
    )

    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]

    assert captured_chunk_ids == ["finance-2", "finance-1"]
    assert [event["type"] for event in events] == ["meta", "token", "sources", "done"]
    assert [source["chunk_id"] for source in events[2]["sources"]] == ["finance-2", "finance-1"]