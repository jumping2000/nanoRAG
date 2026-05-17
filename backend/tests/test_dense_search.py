from types import SimpleNamespace

from config import get_settings
from retrieval.dense_search import DenseRetriever


class StubEmbeddingProvider:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        assert texts == ["SOA servizi architettura orientata ai servizi"]
        return [[0.1, 0.2, 0.3]]


class QueryPointsOnlyClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_collection(self, collection_name: str) -> object:
        return {"collection_name": collection_name}

    def query_points(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            points=[
                SimpleNamespace(
                    payload={
                        "chunk_id": "finance-1",
                        "kb_id": "test",
                        "kb_name": "test",
                        "document_id": "finance-doc",
                        "source": "kb:test/document:finance-doc",
                        "filename": "soa.pdf",
                        "page": 1,
                        "section": "Overview",
                        "text": "SOA overview",
                        "token_count": 3,
                    },
                    score=0.87,
                )
            ]
        )


def test_dense_search_supports_qdrant_query_points_api() -> None:
    settings = get_settings()
    retriever = object.__new__(DenseRetriever)
    retriever.settings = settings
    retriever.embedding_provider = StubEmbeddingProvider()
    retriever.client = QueryPointsOnlyClient()

    results = retriever.search(
        "SOA servizi architettura orientata ai servizi",
        kb_id="test",
        top_k=6,
    )

    assert len(results) == 1
    assert results[0].chunk_id == "finance-1"
    assert results[0].kb_id == "test"
    assert results[0].score == 0.87
    assert retriever.client.calls[0]["collection_name"] == settings.qdrant_collection
    assert retriever.client.calls[0]["limit"] == 6
    assert retriever.client.calls[0]["with_payload"] is True
    assert retriever.client.calls[0]["with_vectors"] is False