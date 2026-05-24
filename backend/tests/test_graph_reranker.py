from __future__ import annotations

from models import RetrievedChunk
from retrieval.graph_reranker import GraphReranker


class FakeGraphStore:
    def __init__(self, summaries: dict[str, dict[str, float | int]]) -> None:
        self.summaries = summaries
        self.calls: list[tuple[str, list[str], float]] = []

    def get_chunk_graph_summary(
        self,
        kb_id: str,
        chunk_ids: list[str],
        min_confidence: float = 0.0,
    ) -> dict[str, dict[str, float | int]]:
        self.calls.append((kb_id, chunk_ids, min_confidence))
        return {chunk_id: self.summaries.get(chunk_id, {}) for chunk_id in chunk_ids}


def _chunk(chunk_id: str, *, score: float, rank: int) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        kb_id="finance",
        kb_name="Finance",
        document_id=f"{chunk_id}-doc",
        source=f"kb:finance/document:{chunk_id}-doc",
        filename=f"{chunk_id}.md",
        page=1,
        section="Overview",
        text=f"content for {chunk_id}",
        token_count=4,
        score=score,
        rank=rank,
    )


def test_graph_reranker_promotes_graph_rich_chunk_when_scores_are_close() -> None:
    chunks = [_chunk("chunk-a", score=0.91, rank=1), _chunk("chunk-b", score=0.90, rank=2)]
    graph_store = FakeGraphStore(
        {
            "chunk-b": {"entity_confidence_sum": 0.8, "relation_confidence_sum": 2.0},
        }
    )
    reranker = GraphReranker(graph_store)

    reranked = reranker.rerank("finance", chunks)

    assert [chunk.chunk_id for chunk in reranked] == ["chunk-b", "chunk-a"]
    assert [chunk.rank for chunk in reranked] == [1, 2]


def test_graph_reranker_prefers_relation_bearing_chunk_over_entity_only_chunk() -> None:
    chunks = [_chunk("chunk-a", score=0.8, rank=1), _chunk("chunk-b", score=0.8, rank=2)]
    graph_store = FakeGraphStore(
        {
            "chunk-a": {"entity_confidence_sum": 2.0, "relation_confidence_sum": 0.0},
            "chunk-b": {"entity_confidence_sum": 1.0, "relation_confidence_sum": 2.0},
        }
    )
    reranker = GraphReranker(graph_store)

    reranked = reranker.rerank("finance", chunks)

    assert [chunk.chunk_id for chunk in reranked] == ["chunk-b", "chunk-a"]


def test_graph_reranker_preserves_original_order_when_graph_signal_is_absent() -> None:
    chunks = [_chunk("chunk-a", score=0.7, rank=1), _chunk("chunk-b", score=0.6, rank=2)]
    graph_store = FakeGraphStore({})
    reranker = GraphReranker(graph_store)

    reranked = reranker.rerank("finance", chunks)

    assert [chunk.chunk_id for chunk in reranked] == ["chunk-a", "chunk-b"]
    assert reranked[0] is chunks[0]
    assert reranked[1] is chunks[1]


def test_graph_reranker_uses_stable_tiebreakers_and_requested_kb() -> None:
    chunks = [_chunk("chunk-b", score=0.8, rank=1), _chunk("chunk-a", score=0.8, rank=2)]
    graph_store = FakeGraphStore(
        {
            "chunk-a": {"entity_confidence_sum": 1.0, "relation_confidence_sum": 1.0},
            "chunk-b": {"entity_confidence_sum": 1.0, "relation_confidence_sum": 1.0},
        }
    )
    reranker = GraphReranker(graph_store)

    reranked = reranker.rerank("architecture", chunks)

    assert [chunk.chunk_id for chunk in reranked] == ["chunk-b", "chunk-a"]
    assert graph_store.calls == [("architecture", ["chunk-b", "chunk-a"], 0.55)]