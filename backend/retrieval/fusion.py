from __future__ import annotations

from collections.abc import Sequence

from models import RetrievedChunk


def reciprocal_rank_fusion(
    result_sets: Sequence[Sequence[RetrievedChunk]],
    limit: int,
    k: int = 60,
) -> list[RetrievedChunk]:
    fused_scores: dict[str, float] = {}
    by_chunk_id: dict[str, RetrievedChunk] = {}

    for result_set in result_sets:
        for rank, item in enumerate(result_set, start=1):
            fused_scores[item.chunk_id] = fused_scores.get(item.chunk_id, 0.0) + 1.0 / (k + rank)
            best = by_chunk_id.get(item.chunk_id)
            if best is None or item.score > best.score:
                by_chunk_id[item.chunk_id] = item

    ranked = sorted(
        by_chunk_id.values(),
        key=lambda item: (fused_scores[item.chunk_id], item.score),
        reverse=True,
    )

    return [
        item.model_copy(update={"score": fused_scores[item.chunk_id], "rank": index})
        for index, item in enumerate(ranked[:limit], start=1)
    ]
