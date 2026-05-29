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

    def search(
        self,
        query: str,
        kb_id: str,
        top_k: int | None = None,
        *,
        expander: object | None = None,
        graph_retriever: object | None = None,
    ) -> list[RetrievedChunk]:
        limit = top_k or self.settings.retrieval_top_k
        started = time.perf_counter()

        # Phase A: Query expansion
        search_query = query
        seed_entities: list[str] = []
        if expander is not None:
            expanded = expander.expand(kb_id, query)
            if expanded.added_terms:
                search_query = expanded.expanded_query
                seed_entities = expanded.matched_entities
                observe(
                    logger,
                    logging.INFO,
                    "retrieval",
                    "query_expansion.completed",
                    kb_id=kb_id,
                    original_query=query,
                    expanded_query=search_query,
                    matched_entities=len(seed_entities),
                    added_terms=len(expanded.added_terms),
                )

        # Phase B: Dense + BM25 on (expanded) query
        try:
            dense_results = self.dense_retriever.search(search_query, kb_id=kb_id, top_k=limit * 2)
        except Exception as error:
            observe(
                logger,
                logging.WARNING,
                "retrieval",
                "dense.failed",
                kb_id=kb_id,
                query_length=len(search_query),
                top_k=limit * 2,
                reason=type(error).__name__,
            )
            dense_results = []

        sparse_results = self.sparse_retriever.search(search_query, kb_id=kb_id, top_k=limit * 2)

        result_sets = [dense_results, sparse_results]

        # Phase C: Graph retrieval
        if graph_retriever is not None:
            graph_query_entities = seed_entities
            if not graph_query_entities and expander is not None:
                expanded_check = expander.expand(kb_id, query)
                graph_query_entities = expanded_check.matched_entities

            if graph_query_entities:
                graph_started = time.perf_counter()
                graph_results = graph_retriever.search(
                    kb_id, graph_query_entities, top_k=self.settings.graph_retrieval_top_k,
                )
                if graph_results:
                    result_sets.append(graph_results)
                observe(
                    logger,
                    logging.INFO,
                    "retrieval",
                    "graph_retrieval.completed",
                    kb_id=kb_id,
                    seeds=len(graph_query_entities),
                    graph_candidates=len(graph_results),
                    elapsed_ms=round((time.perf_counter() - graph_started) * 1000, 2),
                )

        fused_results = reciprocal_rank_fusion(result_sets, limit=limit)
        observe(
            logger,
            logging.INFO,
            "retrieval",
            "hybrid.completed",
            kb_id=kb_id,
            query_length=len(search_query),
            limit=limit,
            dense_results=len(dense_results),
            sparse_results=len(sparse_results),
            graph_augmented=graph_retriever is not None,
            fused_results=len(fused_results),
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return fused_results
