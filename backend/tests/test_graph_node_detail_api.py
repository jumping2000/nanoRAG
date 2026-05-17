from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from models import ChunkMetadata, DocumentRecord
from tests.graph_test_support import GraphTestRuntime, setup_test_runtime


def _store_chunk(runtime: GraphTestRuntime, chunk: ChunkMetadata) -> None:
    runtime.sparse_retriever.upsert([chunk])
    runtime.dense_retriever.upsert([chunk])
    entities, relations = runtime.graph_extractor.extract(chunk)
    runtime.graph_store.replace_chunk(chunk, entities, relations)


def test_graph_node_detail_api_returns_finance_only_relations(tmp_path: Path, monkeypatch) -> None:
    runtime = setup_test_runtime(tmp_path, monkeypatch)
    runtime.catalog.create_kb("finance", "Finance")
    runtime.catalog.create_kb("ops", "Operations")

    runtime.catalog.upsert_document(
        DocumentRecord(
            document_id="finance-doc-a",
            kb_id="finance",
            kb_name="Finance",
            filename="finance-a.md",
            chunk_count=1,
            created_at="2026-05-10T00:00:00+00:00",
        )
    )
    runtime.catalog.upsert_document(
        DocumentRecord(
            document_id="finance-doc-b",
            kb_id="finance",
            kb_name="Finance",
            filename="finance-b.md",
            chunk_count=1,
            created_at="2026-05-10T00:00:00+00:00",
        )
    )
    runtime.catalog.upsert_document(
        DocumentRecord(
            document_id="ops-doc-a",
            kb_id="ops",
            kb_name="Operations",
            filename="ops-a.md",
            chunk_count=1,
            created_at="2026-05-10T00:00:00+00:00",
        )
    )

    _store_chunk(
        runtime,
        ChunkMetadata(
            chunk_id="finance-a-1",
            kb_id="finance",
            kb_name="Finance",
            document_id="finance-doc-a",
            source="kb:finance/document:finance-doc-a",
            filename="finance-a.md",
            page=1,
            section="Overview",
            text="FastAPI uses Qdrant for vector retrieval.",
            token_count=6,
        ),
    )
    _store_chunk(
        runtime,
        ChunkMetadata(
            chunk_id="finance-b-1",
            kb_id="finance",
            kb_name="Finance",
            document_id="finance-doc-b",
            source="kb:finance/document:finance-doc-b",
            filename="finance-b.md",
            page=1,
            section="Overview",
            text="FastAPI runs on Azure.",
            token_count=4,
        ),
    )
    _store_chunk(
        runtime,
        ChunkMetadata(
            chunk_id="ops-a-1",
            kb_id="ops",
            kb_name="Operations",
            document_id="ops-doc-a",
            source="kb:ops/document:ops-doc-a",
            filename="ops-a.md",
            page=1,
            section="Overview",
            text="FastAPI references Contracts.",
            token_count=3,
        ),
    )

    client = TestClient(runtime.api_main.app)
    response = client.get("/kb/finance/graph/node/fastapi")

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")

    payload = response.json()
    assert payload["node"] == {
        "id": "fastapi",
        "label": "FastAPI",
        "entity_type": "service",
        "mentions": 2,
    }
    assert payload["stats"] == {"mentions": 2, "documents": 2, "relations": 2}
    assert [document["document_id"] for document in payload["documents"]] == [
        "finance-doc-a",
        "finance-doc-b",
    ]
    assert {relation["predicate"] for relation in payload["relations"]} == {"uses", "runs_on"}
    assert {relation["counterpart"]["label"] for relation in payload["relations"]} == {
        "Azure",
        "Qdrant",
    }

    evidence_document_ids = {
        evidence["document_id"]
        for relation in payload["relations"]
        for evidence in relation["evidence"]
    }
    assert evidence_document_ids == {"finance-doc-a", "finance-doc-b"}
