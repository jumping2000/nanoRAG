from __future__ import annotations

import logging
import time
from types import SimpleNamespace

from qdrant_client.http import models

from config import Settings
from db.qdrant import build_payload_filter, create_qdrant_client, delete_points_by_filter, ensure_collection
from models import ChunkMetadata, RetrievedChunk
from observability import observe
from providers.embedding_provider import EmbeddingProvider
from rag.embeddings import embed_chunks
from rag.metadata import build_qdrant_point_id

logger = logging.getLogger(__name__)


class DenseRetriever:
    def __init__(self, settings: Settings, embedding_provider: EmbeddingProvider) -> None:
        self.settings = settings
        self.embedding_provider = embedding_provider
        self.client = create_qdrant_client(settings)

    def upsert(self, chunks: list[ChunkMetadata]) -> None:
        if not chunks:
            return

        started = time.perf_counter()

        embeddings = embed_chunks(self.embedding_provider, chunks)
        if not embeddings:
            observe(logger, logging.DEBUG, "dense", "upsert.skipped", reason="no_embeddings")
            return

        ensure_collection(
            client=self.client,
            collection_name=self.settings.qdrant_collection,
            vector_size=len(embeddings[0]),
        )

        points = [
            models.PointStruct(
                id=build_qdrant_point_id(chunk.chunk_id),
                vector=embedding,
                payload=chunk.model_dump(),
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]
        self.client.upsert(
            collection_name=self.settings.qdrant_collection,
            wait=True,
            points=points,
        )
        observe(
            logger,
            logging.DEBUG,
            "dense",
            "upsert.completed",
            kb_id=chunks[0].kb_id,
            points=len(points),
            vector_size=len(embeddings[0]),
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )

    def search(self, query: str, kb_id: str, top_k: int) -> list[RetrievedChunk]:
        started = time.perf_counter()
        if not query.strip():
            observe(logger, logging.DEBUG, "dense", "search.skipped", kb_id=kb_id, reason="empty_query")
            return []
        if not self._collection_exists():
            observe(logger, logging.DEBUG, "dense", "search.skipped", kb_id=kb_id, reason="missing_collection")
            return []

        query_vector = self.embedding_provider.embed_texts([query])[0]
        hits = self._search_points(query_vector=query_vector, kb_id=kb_id, top_k=top_k)

        results = [
            RetrievedChunk(
                **(hit.payload or {}),
                score=float(hit.score),
                rank=index,
            )
            for index, hit in enumerate(hits, start=1)
        ]
        observe(
            logger,
            logging.DEBUG,
            "dense",
            "search.completed",
            kb_id=kb_id,
            query_length=len(query),
            top_k=top_k,
            hits=len(results),
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return results

    def _search_points(self, query_vector: list[float], kb_id: str, top_k: int) -> list[object]:
        if hasattr(self.client, "search"):
            return self.client.search(
                collection_name=self.settings.qdrant_collection,
                query_vector=query_vector,
                query_filter=build_payload_filter(kb_id=kb_id),
                limit=top_k,
                with_payload=True,
            )

        response = self.client.query_points(
            collection_name=self.settings.qdrant_collection,
            query=query_vector,
            query_filter=build_payload_filter(kb_id=kb_id),
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        )
        return list(getattr(response, "points", []))

    def _collection_exists(self) -> bool:
        try:
            self.client.get_collection(self.settings.qdrant_collection)
            return True
        except Exception:
            return False

    def delete_document(self, kb_id: str, document_id: str) -> None:
        if not self._collection_exists():
            return
        delete_points_by_filter(
            client=self.client,
            collection_name=self.settings.qdrant_collection,
            query_filter=build_payload_filter(kb_id=kb_id, document_id=document_id),
        )
        observe(logger, logging.DEBUG, "dense", "document.deleted", kb_id=kb_id, document_id=document_id)

    def delete_kb(self, kb_id: str) -> None:
        if not self._collection_exists():
            return
        delete_points_by_filter(
            client=self.client,
            collection_name=self.settings.qdrant_collection,
            query_filter=build_payload_filter(kb_id=kb_id),
        )
        observe(logger, logging.DEBUG, "dense", "kb.deleted", kb_id=kb_id)
