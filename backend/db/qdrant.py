from __future__ import annotations

import logging
import time
from collections.abc import Sequence

from qdrant_client import QdrantClient
from qdrant_client.http import models

from config import Settings
from observability import observe

logger = logging.getLogger(__name__)


def create_qdrant_client(settings: Settings) -> QdrantClient:
    observe(logger, logging.DEBUG, "qdrant", "client.created", url=settings.qdrant_url)
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)


def collection_exists(
    client: QdrantClient,
    collection_name: str,
) -> bool:
    try:
        client.get_collection(collection_name)
        return True
    except Exception:
        return False


def ensure_collection(
    client: QdrantClient,
    collection_name: str,
    vector_size: int,
) -> None:
    started = time.perf_counter()
    try:
        client.get_collection(collection_name)
        observe(
            logger,
            logging.DEBUG,
            "qdrant",
            "collection.ready",
            collection_name=collection_name,
            vector_size=vector_size,
            existed=True,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return
    except Exception:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )
        observe(
            logger,
            logging.DEBUG,
            "qdrant",
            "collection.ready",
            collection_name=collection_name,
            vector_size=vector_size,
            existed=False,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
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
    started = time.perf_counter()
    client.delete(
        collection_name=collection_name,
        points_selector=models.FilterSelector(filter=query_filter),
        wait=True,
    )
    observe(
        logger,
        logging.DEBUG,
        "qdrant",
        "points.deleted",
        collection_name=collection_name,
        must_conditions=len(query_filter.must or []),
        elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
    )


def delete_points_by_ids(
    client: QdrantClient,
    collection_name: str,
    point_ids: Sequence[object],
) -> int:
    if not point_ids:
        return 0

    started = time.perf_counter()
    client.delete(
        collection_name=collection_name,
        points_selector=models.PointIdsList(points=list(point_ids)),
        wait=True,
    )
    observe(
        logger,
        logging.DEBUG,
        "qdrant",
        "points.deleted_by_id",
        collection_name=collection_name,
        points=len(point_ids),
        elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    return len(point_ids)


def list_orphan_point_ids(
    client: QdrantClient,
    collection_name: str,
    limit: int = 256,
) -> list[object]:
    if not collection_exists(client, collection_name):
        return []

    orphan_ids: list[object] = []
    offset: object | None = None
    while True:
        records, offset = client.scroll(
            collection_name=collection_name,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for record in records:
            payload = getattr(record, "payload", None) or {}
            if not payload.get("kb_id"):
                orphan_ids.append(getattr(record, "id"))
        if offset is None:
            break

    observe(
        logger,
        logging.DEBUG,
        "qdrant",
        "orphans.listed",
        collection_name=collection_name,
        orphans=len(orphan_ids),
    )
    return orphan_ids


def delete_collection(
    client: QdrantClient,
    collection_name: str,
) -> bool:
    if not collection_exists(client, collection_name):
        return False

    started = time.perf_counter()
    client.delete_collection(collection_name=collection_name)
    observe(
        logger,
        logging.DEBUG,
        "qdrant",
        "collection.deleted",
        collection_name=collection_name,
        elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    return True

