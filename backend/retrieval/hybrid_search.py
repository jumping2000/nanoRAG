from __future__ import annotations

from config import Settings
from models import RetrievedChunk
from retrieval.dense_search import DenseRetriever
from retrieval.fusion import reciprocal_rank_fusion
from retrieval.sparse_search import SparseRetriever


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

    def search(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        limit = top_k or self.settings.retrieval_top_k

        try:
            dense_results = self.dense_retriever.search(query, top_k=limit * 2)
        except Exception:
            dense_results = []

        sparse_results = self.sparse_retriever.search(query, top_k=limit * 2)
        return reciprocal_rank_fusion([dense_results, sparse_results], limit=limit)
