from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tests.graph_test_support import setup_test_runtime


def _upload_markdown(client: TestClient, kb_id: str, filename: str, text: str) -> dict[str, object]:
    response = client.post(
        f"/kb/{kb_id}/upload",
        files=[("files", (filename, text.encode("utf-8"), "text/markdown"))],
    )

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")

    payload = response.json()
    assert len(payload["uploaded"]) == 1
    return payload["uploaded"][0]


def test_graph_smoke_api_create_upload_graph_and_delete(tmp_path: Path, monkeypatch) -> None:
    runtime = setup_test_runtime(tmp_path, monkeypatch)
    client = TestClient(runtime.api_main.app)

    create_architecture = client.post("/kb", json={"id": "architecture", "name": "Architecture"})
    assert create_architecture.status_code == 200
    assert create_architecture.headers.get("X-Request-ID")

    create_operations = client.post("/kb", json={"id": "operations", "name": "Operations"})
    assert create_operations.status_code == 200
    assert create_operations.headers.get("X-Request-ID")

    architecture_doc_a = _upload_markdown(
        client,
        "architecture",
        "architecture-a.md",
        "# Overview\n\nFastAPI uses Qdrant for vector retrieval.\n",
    )
    architecture_doc_b = _upload_markdown(
        client,
        "architecture",
        "architecture-b.md",
        "# Overview\n\nFastAPI runs on Azure.\n",
    )
    operations_doc = _upload_markdown(
        client,
        "operations",
        "operations-a.md",
        "# Overview\n\nKubernetes manages Helm deployments.\n",
    )

    kb_response = client.get("/kb")
    assert kb_response.status_code == 200
    kb_map = {item["id"]: item for item in kb_response.json()}
    assert kb_map["architecture"]["documents"] == 2
    assert kb_map["operations"]["documents"] == 1

    architecture_graph = client.get("/kb/architecture/graph")
    assert architecture_graph.status_code == 200
    architecture_labels = {node["label"] for node in architecture_graph.json()["nodes"]}
    assert "FastAPI" in architecture_labels
    assert "Kubernetes" not in architecture_labels

    operations_graph = client.get("/kb/operations/graph")
    assert operations_graph.status_code == 200
    operations_labels = {node["label"] for node in operations_graph.json()["nodes"]}
    assert "Kubernetes" in operations_labels
    assert "FastAPI" not in operations_labels

    architecture_detail = client.get("/kb/architecture/graph/node/fastapi")
    assert architecture_detail.status_code == 200
    assert architecture_detail.headers.get("X-Request-ID")
    architecture_detail_payload = architecture_detail.json()
    assert architecture_detail_payload["stats"] == {"mentions": 2, "documents": 2, "relations": 2}
    assert {document["document_id"] for document in architecture_detail_payload["documents"]} == {
        str(architecture_doc_a["document_id"]),
        str(architecture_doc_b["document_id"]),
    }
    assert {relation["predicate"] for relation in architecture_detail_payload["relations"]} == {
        "uses",
        "runs_on",
    }

    delete_response = client.delete(f"/kb/architecture/documents/{architecture_doc_a['document_id']}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"status": "ok"}
    assert delete_response.headers.get("X-Request-ID")

    kb_response_after_delete = client.get("/kb")
    assert kb_response_after_delete.status_code == 200
    kb_map_after_delete = {item["id"]: item for item in kb_response_after_delete.json()}
    assert kb_map_after_delete["architecture"]["documents"] == 1
    assert kb_map_after_delete["operations"]["documents"] == 1

    architecture_detail_after_delete = client.get("/kb/architecture/graph/node/fastapi")
    assert architecture_detail_after_delete.status_code == 200
    architecture_detail_after_delete_payload = architecture_detail_after_delete.json()
    assert architecture_detail_after_delete_payload["stats"] == {
        "mentions": 1,
        "documents": 1,
        "relations": 1,
    }
    assert architecture_detail_after_delete_payload["documents"] == [
        {
            "document_id": architecture_doc_b["document_id"],
            "filename": "architecture-b.md",
            "mention_count": 1,
        }
    ]
    assert [relation["predicate"] for relation in architecture_detail_after_delete_payload["relations"]] == [
        "runs_on"
    ]
    assert [relation["counterpart"]["label"] for relation in architecture_detail_after_delete_payload["relations"]] == [
        "Azure"
    ]

    operations_documents = client.get("/kb/operations/documents")
    assert operations_documents.status_code == 200
    assert [document["document_id"] for document in operations_documents.json()] == [
        operations_doc["document_id"]
    ]

    operations_graph_after_delete = client.get("/kb/operations/graph")
    assert operations_graph_after_delete.status_code == 200
    operations_labels_after_delete = {
        node["label"] for node in operations_graph_after_delete.json()["nodes"]
    }
    assert "Kubernetes" in operations_labels_after_delete
    assert "FastAPI" not in operations_labels_after_delete