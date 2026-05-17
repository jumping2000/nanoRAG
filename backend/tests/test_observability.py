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