from models import RetrievedChunk
from rag.metadata import build_qdrant_point_id
from retrieval.fusion import reciprocal_rank_fusion


def _chunk(chunk_id: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        source="test",
        filename="doc.md",
        page=1,
        section="Section",
        text=f"Text for {chunk_id}",
        token_count=10,
        score=score,
        rank=1,
    )


def test_rrf_prefers_items_present_in_multiple_rankings() -> None:
    dense = [_chunk("a", 0.9), _chunk("b", 0.7)]
    sparse = [_chunk("b", 14.0), _chunk("c", 10.0)]

    fused = reciprocal_rank_fusion([dense, sparse], limit=3)

    assert fused[0].chunk_id == "b"
    assert {item.chunk_id for item in fused} == {"a", "b", "c"}


def test_qdrant_point_id_is_deterministic_uuid() -> None:
    first = build_qdrant_point_id("architettura-soa-1-overview-0-abc123")
    second = build_qdrant_point_id("architettura-soa-1-overview-0-abc123")

    assert first == second
    assert len(first) == 36
    assert first.count("-") == 4
