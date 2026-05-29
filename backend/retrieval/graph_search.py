"""Graph-based retrieval — pulls chunk candidates from knowledge graph evidence."""

from __future__ import annotations

import logging

from models import RetrievedChunk
from observability import observe

logger = logging.getLogger(__name__)


class GraphRetriever:
    def __init__(self, graph_store, sparse_retriever) -> None:
        self._graph_store = graph_store
        self._sparse_retriever = sparse_retriever

    def search(
        self, kb_id: str, seed_entities: list[str], top_k: int,
    ) -> list[RetrievedChunk]:
        if not seed_entities:
            return []

        candidates = self._graph_store.get_chunk_candidates_for_entities(
            kb_id, seed_entities, limit=top_k * 3,
        )

        scored = []
        for c in candidates:
            entity_count = int(c["entity_count"])
            relation_count = int(c["relation_count"])
            confidence_sum = float(c["confidence_sum"])
            score = (entity_count * 0.35 + relation_count * 0.65) * max(confidence_sum, 1.0)
            scored.append((str(c["chunk_id"]), score))

        scored.sort(key=lambda x: x[1], reverse=True)
        scored = scored[:top_k]

        all_chunks = self._sparse_retriever.list_chunks(kb_id)
        by_id = {chunk.chunk_id: chunk for chunk in all_chunks}

        results: list[RetrievedChunk] = []
        for rank, (chunk_id, score) in enumerate(scored, start=1):
            chunk = by_id.get(chunk_id)
            if chunk is None:
                continue
            results.append(
                RetrievedChunk(
                    **chunk.model_dump(),
                    score=score,
                    rank=rank,
                ),
            )

        observe(
            logger,
            logging.INFO,
            "retrieval",
            "graph_retrieval.completed",
            kb_id=kb_id,
            seeds=len(seed_entities),
            candidates=len(scored),
            materialized=len(results),
        )
        return results
