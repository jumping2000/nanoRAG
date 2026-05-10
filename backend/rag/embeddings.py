from __future__ import annotations

from collections.abc import Iterable

from models import ChunkMetadata
from providers.embedding_provider import EmbeddingProvider


def embed_chunks(
    embedding_provider: EmbeddingProvider,
    chunks: Iterable[ChunkMetadata],
    batch_size: int = 16,
) -> list[list[float]]:
    chunk_list = list(chunks)
    embeddings: list[list[float]] = []

    for start in range(0, len(chunk_list), batch_size):
        batch = chunk_list[start : start + batch_size]
        embeddings.extend(
            embedding_provider.embed_texts([chunk.text for chunk in batch]),
        )

    return embeddings
