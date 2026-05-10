from __future__ import annotations

from qdrant_client.http import models

from config import Settings
from db.qdrant import create_qdrant_client, ensure_collection
from models import ChunkMetadata, RetrievedChunk
from providers.embedding_provider import EmbeddingProvider
from rag.embeddings import embed_chunks
from rag.metadata import build_qdrant_point_id


class DenseRetriever:
    def __init__(self, settings: Settings, embedding_provider: EmbeddingProvider) -> None:
        self.settings = settings
        self.embedding_provider = embedding_provider
        self.client = create_qdrant_client(settings)

    def upsert(self, chunks: list[ChunkMetadata]) -> None:
        if not chunks:
            return

        embeddings = embed_chunks(self.embedding_provider, chunks)
        if not embeddings:
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

    def search(self, query: str, top_k: int) -> list[RetrievedChunk]:
        if not query.strip() or not self._collection_exists():
            return []

        query_vector = self.embedding_provider.embed_texts([query])[0]
        hits = self.client.search(
            collection_name=self.settings.qdrant_collection,
            query_vector=query_vector,
            limit=top_k,
            with_payload=True,
        )

        return [
            RetrievedChunk(
                **(hit.payload or {}),
                score=float(hit.score),
                rank=index,
            )
            for index, hit in enumerate(hits, start=1)
        ]

    def _collection_exists(self) -> bool:
        try:
            self.client.get_collection(self.settings.qdrant_collection)
            return True
        except Exception:
            return False
