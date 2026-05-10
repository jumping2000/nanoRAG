from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.http import models

from config import Settings


def create_qdrant_client(settings: Settings) -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)


def ensure_collection(
    client: QdrantClient,
    collection_name: str,
    vector_size: int,
) -> None:
    try:
        client.get_collection(collection_name)
        return
    except Exception:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )


def build_payload_filter(
    kb_id: str,
    document_id: str | None = None,
) -> models.Filter:
    must: list[models.Condition] = [
        models.FieldCondition(
            key="kb_id",
            match=models.MatchValue(value=kb_id),
        ),
    ]
    if document_id is not None:
        must.append(
            models.FieldCondition(
                key="document_id",
                match=models.MatchValue(value=document_id),
            ),
        )

    return models.Filter(must=must)


def delete_points_by_filter(
    client: QdrantClient,
    collection_name: str,
    query_filter: models.Filter,
) -> None:
    client.delete(
        collection_name=collection_name,
        points_selector=models.FilterSelector(filter=query_filter),
        wait=True,
    )
