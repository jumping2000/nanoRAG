from __future__ import annotations

import logging
import time

from config import Settings
from models import RetrievedChunk
from observability import observe
from retrieval.dense_search import DenseRetriever
from retrieval.fusion import reciprocal_rank_fusion
from retrieval.sparse_search import SparseRetriever

logger = logging.getLogger(__name__)


class HybridRetriever:
    def __init__(
        self,
        settings: Settings,
        dense_retriever: DenseRetriever,
        sparse_retriever: SparseRetriever,
    ) -> None:
        self.settings = settings
        self.dense_retriever = dense_retriever
        self.sparse_retriever = sparse_retriever

    def search(self, query: str, kb_id: str, top_k: int | None = None) -> list[RetrievedChunk]:
        limit = top_k or self.settings.retrieval_top_k
        started = time.perf_counter()

        try:
            dense_results = self.dense_retriever.search(query, kb_id=kb_id, top_k=limit * 2)
        except Exception as error:
            observe(
                logger,
                logging.WARNING,
                "retrieval",
                "dense.failed",
                kb_id=kb_id,
                query_length=len(query),
                top_k=limit * 2,
                reason=type(error).__name__,
            )
            dense_results = []

        sparse_results = self.sparse_retriever.search(query, kb_id=kb_id, top_k=limit * 2)
        fused_results = reciprocal_rank_fusion([dense_results, sparse_results], limit=limit)
        observe(
            logger,
            logging.INFO,
            "retrieval",
            "hybrid.completed",
            kb_id=kb_id,
            query_length=len(query),
            limit=limit,
            dense_results=len(dense_results),
            sparse_results=len(sparse_results),
            fused_results=len(fused_results),
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return fused_results
