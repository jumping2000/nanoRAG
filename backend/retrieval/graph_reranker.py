from __future__ import annotations

import logging
from collections.abc import Sequence

from models import RetrievedChunk
from observability import observe

logger = logging.getLogger(__name__)


class GraphReranker:
    def __init__(
        self,
        graph_store,
        *,
        min_confidence: float = 0.55,
        retrieval_weight: float = 0.75,
        graph_weight: float = 0.25,
        entity_weight: float = 0.35,
        relation_weight: float = 0.65,
    ) -> None:
        self.graph_store = graph_store
        self.min_confidence = max(0.0, min(1.0, min_confidence))
        self.retrieval_weight = retrieval_weight
        self.graph_weight = graph_weight
        self.entity_weight = entity_weight
        self.relation_weight = relation_weight

    def rerank(self, kb_id: str, chunks: Sequence[RetrievedChunk]) -> list[RetrievedChunk]:
        if len(chunks) < 2:
            return list(chunks)

        original_chunks = list(chunks)
        summaries = self.graph_store.get_chunk_graph_summary(
            kb_id,
            [chunk.chunk_id for chunk in original_chunks],
            min_confidence=self.min_confidence,
        )
        graph_strengths = {
            chunk.chunk_id: self._graph_strength(summaries.get(chunk.chunk_id, {}))
            for chunk in original_chunks
        }
        chunks_with_signal = sum(1 for strength in graph_strengths.values() if strength > 0.0)

        if chunks_with_signal == 0:
            observe(
                logger,
                logging.DEBUG,
                "retrieval",
                "graph_rerank.completed",
                kb_id=kb_id,
                chunk_count=len(original_chunks),
                chunks_with_graph_signal=0,
                order_changed=False,
            )
            return original_chunks

        retrieval_scores = [max(0.0, float(chunk.score)) for chunk in original_chunks]
        retrieval_norms = self._normalize(retrieval_scores)
        graph_norms = self._normalize([graph_strengths[chunk.chunk_id] for chunk in original_chunks])
        rescored = []
        for index, chunk in enumerate(original_chunks):
            final_score = (
                self.retrieval_weight * retrieval_norms[index]
                + self.graph_weight * graph_norms[index]
            )
            rescored.append((final_score, chunk))

        ordered = sorted(
            rescored,
            key=lambda item: (-item[0], item[1].rank, item[1].chunk_id),
        )
        reranked = [
            chunk.model_copy(update={"score": score, "rank": rank})
            for rank, (score, chunk) in enumerate(ordered, start=1)
        ]
        order_changed = any(
            previous.chunk_id != current.chunk_id
            for previous, current in zip(original_chunks, reranked, strict=False)
        )
        observe(
            logger,
            logging.DEBUG,
            "retrieval",
            "graph_rerank.completed",
            kb_id=kb_id,
            chunk_count=len(original_chunks),
            chunks_with_graph_signal=chunks_with_signal,
            order_changed=order_changed,
        )
        return reranked

    def _graph_strength(self, summary: dict[str, float | int]) -> float:
        entity_strength = float(summary.get("entity_confidence_sum", 0.0) or 0.0)
        relation_strength = float(summary.get("relation_confidence_sum", 0.0) or 0.0)
        return self.entity_weight * entity_strength + self.relation_weight * relation_strength

    @staticmethod
    def _normalize(values: Sequence[float]) -> list[float]:
        if not values:
            return []

        maximum = max(values)
        if maximum <= 0.0:
            return [0.0 for _ in values]
        return [float(value) / maximum for value in values]