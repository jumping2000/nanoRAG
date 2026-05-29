from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path

from config import Settings
from models import (
    ChunkMetadata,
    ExtractedEntity,
    ExtractedRelation,
    GraphEdge,
    GraphEvidence,
    GraphNodeDetail,
    GraphNodeDocument,
    GraphNodeRelation,
    GraphNode,
    GraphSnapshot,
    GraphStats,
)
from observability import observe

logger = logging.getLogger(__name__)


class GraphStore:
    def __init__(self, settings: Settings) -> None:
        self.path = Path(settings.graph_store_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def get_chunk_graph_summary(
        self,
        kb_id: str,
        chunk_ids: list[str],
        min_confidence: float = 0.0,
    ) -> dict[str, dict[str, float | int]]:
        started = time.perf_counter()
        ordered_chunk_ids = list(dict.fromkeys(chunk_ids))
        if not ordered_chunk_ids:
            return {}

        placeholders = ", ".join("?" for _ in ordered_chunk_ids)
        entity_params: list[object] = [kb_id, *ordered_chunk_ids, float(min_confidence)]
        relation_params: list[object] = [kb_id, *ordered_chunk_ids, float(min_confidence)]
        summaries: dict[str, dict[str, float | int]] = {
            chunk_id: {
                "entity_count": 0,
                "entity_confidence_sum": 0.0,
                "relation_count": 0,
                "relation_confidence_sum": 0.0,
            }
            for chunk_id in ordered_chunk_ids
        }

        with self._connect() as connection:
            entity_rows = connection.execute(
                f"""
                SELECT chunk_id, COUNT(*) AS entity_count, COALESCE(SUM(confidence), 0.0) AS entity_confidence_sum
                FROM entity_mentions
                WHERE kb_id = ? AND chunk_id IN ({placeholders}) AND confidence >= ?
                GROUP BY chunk_id
                """,
                entity_params,
            ).fetchall()
            relation_rows = connection.execute(
                f"""
                SELECT chunk_id, COUNT(*) AS relation_count, COALESCE(SUM(confidence), 0.0) AS relation_confidence_sum
                FROM relation_mentions
                WHERE kb_id = ? AND chunk_id IN ({placeholders}) AND confidence >= ?
                GROUP BY chunk_id
                """,
                relation_params,
            ).fetchall()

        for row in entity_rows:
            chunk_id = str(row["chunk_id"])
            bucket = summaries.setdefault(
                chunk_id,
                {
                    "entity_count": 0,
                    "entity_confidence_sum": 0.0,
                    "relation_count": 0,
                    "relation_confidence_sum": 0.0,
                },
            )
            bucket["entity_count"] = int(row["entity_count"])
            bucket["entity_confidence_sum"] = float(row["entity_confidence_sum"] or 0.0)

        for row in relation_rows:
            chunk_id = str(row["chunk_id"])
            bucket = summaries.setdefault(
                chunk_id,
                {
                    "entity_count": 0,
                    "entity_confidence_sum": 0.0,
                    "relation_count": 0,
                    "relation_confidence_sum": 0.0,
                },
            )
            bucket["relation_count"] = int(row["relation_count"])
            bucket["relation_confidence_sum"] = float(row["relation_confidence_sum"] or 0.0)

        observe(
            logger,
            logging.DEBUG,
            "graph_store",
            "chunk_summary.loaded",
            kb_id=kb_id,
            chunk_count=len(ordered_chunk_ids),
            chunks_with_signal=sum(
                1
                for bucket in summaries.values()
                if int(bucket["entity_count"]) > 0 or int(bucket["relation_count"]) > 0
            ),
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return summaries

    def replace_chunk(
        self,
        chunk: ChunkMetadata,
        entities: list[ExtractedEntity],
        relations: list[ExtractedRelation],
    ) -> None:
        started = time.perf_counter()
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM entity_mentions WHERE kb_id = ? AND chunk_id = ?",
                (chunk.kb_id, chunk.chunk_id),
            )
            connection.execute(
                "DELETE FROM relation_mentions WHERE kb_id = ? AND chunk_id = ?",
                (chunk.kb_id, chunk.chunk_id),
            )

            entity_rows = [
                (
                    chunk.kb_id,
                    chunk.document_id,
                    chunk.chunk_id,
                    entity.canonical_id,
                    entity.label,
                    entity.entity_type,
                    entity.confidence,
                    chunk.filename,
                    chunk.page,
                    chunk.section,
                    self._snippet(chunk.text),
                )
                for entity in entities
            ]
            relation_rows = [
                (
                    chunk.kb_id,
                    chunk.document_id,
                    chunk.chunk_id,
                    self._edge_id(relation.source.canonical_id, relation.predicate, relation.target.canonical_id),
                    relation.source.canonical_id,
                    relation.source.label,
                    relation.source.entity_type,
                    relation.predicate,
                    relation.target.canonical_id,
                    relation.target.label,
                    relation.target.entity_type,
                    relation.confidence,
                    chunk.filename,
                    chunk.page,
                    chunk.section,
                    self._snippet(chunk.text),
                )
                for relation in relations
            ]

            if entity_rows:
                connection.executemany(
                    """
                    INSERT INTO entity_mentions (
                        kb_id, document_id, chunk_id, entity_id, label, entity_type, confidence,
                        filename, page, section, snippet
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    entity_rows,
                )
            if relation_rows:
                connection.executemany(
                    """
                    INSERT INTO relation_mentions (
                        kb_id, document_id, chunk_id, edge_id, source_id, source_label, source_type,
                        predicate, target_id, target_label, target_type, confidence,
                        filename, page, section, snippet
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    relation_rows,
                )
        observe(
            logger,
            logging.DEBUG,
            "graph_store",
            "chunk.replaced",
            kb_id=chunk.kb_id,
            chunk_id=chunk.chunk_id,
            entities=len(entities),
            relations=len(relations),
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )

    def delete_document(self, kb_id: str, document_id: str) -> None:
        started = time.perf_counter()
        with self._connect() as connection:
            entity_cursor = connection.execute(
                "DELETE FROM entity_mentions WHERE kb_id = ? AND document_id = ?",
                (kb_id, document_id),
            )
            relation_cursor = connection.execute(
                "DELETE FROM relation_mentions WHERE kb_id = ? AND document_id = ?",
                (kb_id, document_id),
            )
        observe(
            logger,
            logging.DEBUG,
            "graph_store",
            "document.deleted",
            kb_id=kb_id,
            document_id=document_id,
            entity_rows=entity_cursor.rowcount,
            relation_rows=relation_cursor.rowcount,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )

    def delete_kb(self, kb_id: str) -> None:
        started = time.perf_counter()
        with self._connect() as connection:
            entity_cursor = connection.execute("DELETE FROM entity_mentions WHERE kb_id = ?", (kb_id,))
            relation_cursor = connection.execute("DELETE FROM relation_mentions WHERE kb_id = ?", (kb_id,))
        observe(
            logger,
            logging.DEBUG,
            "graph_store",
            "kb.deleted",
            kb_id=kb_id,
            entity_rows=entity_cursor.rowcount,
            relation_rows=relation_cursor.rowcount,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )

    def get_snapshot(self, kb_id: str, limit: int = 18, min_weight: int = 1) -> GraphSnapshot:
        started = time.perf_counter()
        with self._connect() as connection:
            entity_rows = connection.execute(
                """
                SELECT entity_id, label, entity_type, confidence, filename, page, section, snippet, document_id, chunk_id
                FROM entity_mentions
                WHERE kb_id = ?
                ORDER BY rowid ASC
                """,
                (kb_id,),
            ).fetchall()
            relation_rows = connection.execute(
                """
                SELECT edge_id, source_id, source_label, source_type, predicate, target_id, target_label,
                       target_type, confidence, filename, page, section, snippet, document_id, chunk_id
                FROM relation_mentions
                WHERE kb_id = ?
                ORDER BY rowid ASC
                """,
                (kb_id,),
            ).fetchall()

        entity_aggregate: dict[str, dict[str, object]] = {}
        for row in entity_rows:
            bucket = entity_aggregate.setdefault(
                row[0],
                {"labels": {}, "types": {}, "mentions": 0},
            )
            labels = bucket["labels"]
            types = bucket["types"]
            assert isinstance(labels, dict)
            assert isinstance(types, dict)
            labels[row[1]] = labels.get(row[1], 0) + 1
            types[row[2]] = types.get(row[2], 0) + 1
            bucket["mentions"] = int(bucket["mentions"]) + 1

        edge_aggregate: dict[tuple[str, str, str], dict[str, object]] = {}
        for row in relation_rows:
            key = (row[1], row[4], row[5])
            bucket = edge_aggregate.setdefault(
                key,
                {"id": row[0], "weight": 0, "evidence": []},
            )
            bucket["weight"] = int(bucket["weight"]) + 1
            evidence = bucket["evidence"]
            assert isinstance(evidence, list)
            if len(evidence) < 3:
                evidence.append(
                    GraphEvidence(
                        chunk_id=row[14],
                        document_id=row[13],
                        filename=row[9],
                        page=row[10],
                        section=row[11],
                        snippet=row[12],
                        confidence=row[8],
                    )
                )

        sorted_edges = sorted(
            (
                GraphEdge(
                    id=str(bucket["id"]),
                    source=source_id,
                    target=target_id,
                    predicate=predicate,
                    weight=int(bucket["weight"]),
                    evidence=list(bucket["evidence"]),
                )
                for (source_id, predicate, target_id), bucket in edge_aggregate.items()
                if int(bucket["weight"]) >= min_weight
            ),
            key=lambda edge: (-edge.weight, edge.predicate, edge.source, edge.target),
        )[:limit]

        node_ids = {edge.source for edge in sorted_edges} | {edge.target for edge in sorted_edges}
        if not node_ids:
            node_ids = {
                entity_id
                for entity_id, bucket in sorted(
                    entity_aggregate.items(),
                    key=lambda item: (-int(item[1]["mentions"]), item[0]),
                )[: max(8, limit)]
            }

        nodes = sorted(
            (
                GraphNode(
                    id=entity_id,
                    label=self._top_key(entity_aggregate[entity_id]["labels"]),
                    entity_type=self._top_key(entity_aggregate[entity_id]["types"]),
                    mentions=int(entity_aggregate[entity_id]["mentions"]),
                )
                for entity_id in node_ids
                if entity_id in entity_aggregate
            ),
            key=lambda node: (-node.mentions, node.label),
        )

        snapshot = GraphSnapshot(
            kb_id=kb_id,
            nodes=nodes,
            edges=sorted_edges,
            stats=GraphStats(
                nodes=len(nodes),
                edges=len(sorted_edges),
                mentions=len(entity_rows),
            ),
        )
        observe(
            logger,
            logging.DEBUG,
            "graph_store",
            "snapshot.loaded",
            kb_id=kb_id,
            limit=limit,
            min_weight=min_weight,
            entity_rows=len(entity_rows),
            relation_rows=len(relation_rows),
            nodes=snapshot.stats.nodes,
            edges=snapshot.stats.edges,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return snapshot

    def get_node_detail(self, kb_id: str, entity_id: str, evidence_limit: int = 12) -> GraphNodeDetail:
        started = time.perf_counter()
        with self._connect() as connection:
            entity_rows = connection.execute(
                """
                SELECT entity_id, label, entity_type, confidence, filename, page, section, snippet, document_id, chunk_id
                FROM entity_mentions
                WHERE kb_id = ? AND entity_id = ?
                ORDER BY rowid ASC
                """,
                (kb_id, entity_id),
            ).fetchall()
            relation_rows = connection.execute(
                """
                SELECT edge_id, source_id, source_label, source_type, predicate, target_id, target_label,
                       target_type, confidence, filename, page, section, snippet, document_id, chunk_id
                FROM relation_mentions
                WHERE kb_id = ? AND (source_id = ? OR target_id = ?)
                ORDER BY rowid ASC
                """,
                (kb_id, entity_id, entity_id),
            ).fetchall()

        if not entity_rows:
            raise LookupError(f"Graph node not found: {entity_id}")

        label_counts: dict[str, int] = {}
        type_counts: dict[str, int] = {}
        documents_by_id: dict[str, GraphNodeDocument] = {}
        for row in entity_rows:
            label = str(row["label"])
            entity_type = str(row["entity_type"])
            label_counts[label] = label_counts.get(label, 0) + 1
            type_counts[entity_type] = type_counts.get(entity_type, 0) + 1

            document_id = str(row["document_id"])
            document = documents_by_id.get(document_id)
            if document is None:
                documents_by_id[document_id] = GraphNodeDocument(
                    document_id=document_id,
                    filename=str(row["filename"]),
                    mention_count=1,
                )
            else:
                document.mention_count += 1

        node = GraphNode(
            id=entity_id,
            label=self._top_key(label_counts),
            entity_type=self._top_key(type_counts),
            mentions=len(entity_rows),
        )

        relation_buckets: dict[tuple[str, str, str], dict[str, object]] = {}
        for row in relation_rows:
            is_outgoing = str(row["source_id"]) == entity_id
            direction = "outgoing" if is_outgoing else "incoming"
            counterpart_id = str(row["target_id"] if is_outgoing else row["source_id"])
            counterpart_label = str(row["target_label"] if is_outgoing else row["source_label"])
            counterpart_type = str(row["target_type"] if is_outgoing else row["source_type"])
            key = (direction, str(row["predicate"]), counterpart_id)
            bucket = relation_buckets.setdefault(
                key,
                {
                    "edge_id": str(row["edge_id"]),
                    "weight": 0,
                    "counterpart_label_counts": {},
                    "counterpart_type_counts": {},
                    "evidence": [],
                },
            )
            bucket["weight"] = int(bucket["weight"]) + 1

            label_bucket = bucket["counterpart_label_counts"]
            type_bucket = bucket["counterpart_type_counts"]
            evidence = bucket["evidence"]
            assert isinstance(label_bucket, dict)
            assert isinstance(type_bucket, dict)
            assert isinstance(evidence, list)
            label_bucket[counterpart_label] = label_bucket.get(counterpart_label, 0) + 1
            type_bucket[counterpart_type] = type_bucket.get(counterpart_type, 0) + 1
            if len(evidence) < evidence_limit:
                evidence.append(
                    GraphEvidence(
                        chunk_id=str(row["chunk_id"]),
                        document_id=str(row["document_id"]),
                        filename=str(row["filename"]),
                        page=row["page"],
                        section=row["section"],
                        snippet=str(row["snippet"]),
                        confidence=float(row["confidence"]),
                    )
                )

        relations = sorted(
            (
                GraphNodeRelation(
                    edge_id=str(bucket["edge_id"]),
                    predicate=predicate,
                    direction=direction,
                    counterpart=GraphNode(
                        id=counterpart_id,
                        label=self._top_key(bucket["counterpart_label_counts"]),
                        entity_type=self._top_key(bucket["counterpart_type_counts"]),
                        mentions=0,
                    ),
                    weight=int(bucket["weight"]),
                    evidence=list(bucket["evidence"]),
                )
                for (direction, predicate, counterpart_id), bucket in relation_buckets.items()
            ),
            key=lambda relation: (-relation.weight, relation.predicate, relation.counterpart.label),
        )
        documents = sorted(
            documents_by_id.values(),
            key=lambda document: (-document.mention_count, document.filename, document.document_id),
        )
        detail = GraphNodeDetail(
            node=node,
            relations=relations,
            documents=documents,
            stats={
                "mentions": node.mentions,
                "documents": len(documents),
                "relations": len(relations),
            },
        )
        observe(
            logger,
            logging.DEBUG,
            "graph_store",
            "node_detail.loaded",
            kb_id=kb_id,
            entity_id=entity_id,
            mentions=detail.stats["mentions"],
            documents=detail.stats["documents"],
            relations=detail.stats["relations"],
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return detail

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS entity_mentions (
                    kb_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    filename TEXT NOT NULL,
                    page INTEGER,
                    section TEXT,
                    snippet TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS relation_mentions (
                    kb_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    edge_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    source_label TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    target_label TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    filename TEXT NOT NULL,
                    page INTEGER,
                    section TEXT,
                    snippet TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_entity_mentions_kb ON entity_mentions (kb_id);
                CREATE INDEX IF NOT EXISTS idx_entity_mentions_chunk ON entity_mentions (kb_id, chunk_id);
                CREATE INDEX IF NOT EXISTS idx_entity_mentions_document ON entity_mentions (kb_id, document_id);
                CREATE INDEX IF NOT EXISTS idx_entity_mentions_entity ON entity_mentions (kb_id, entity_id);
                CREATE INDEX IF NOT EXISTS idx_relation_mentions_kb ON relation_mentions (kb_id);
                CREATE INDEX IF NOT EXISTS idx_relation_mentions_chunk ON relation_mentions (kb_id, chunk_id);
                CREATE INDEX IF NOT EXISTS idx_relation_mentions_document ON relation_mentions (kb_id, document_id);
                CREATE INDEX IF NOT EXISTS idx_relation_mentions_source ON relation_mentions (kb_id, source_id);
                CREATE INDEX IF NOT EXISTS idx_relation_mentions_target ON relation_mentions (kb_id, target_id);
                CREATE INDEX IF NOT EXISTS idx_relation_mentions_edge ON relation_mentions (kb_id, edge_id);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _edge_id(source_id: str, predicate: str, target_id: str) -> str:
        return f"{source_id}:{predicate}:{target_id}"

    @staticmethod
    def _snippet(text: str, limit: int = 220) -> str:
        compact = " ".join(text.split())
        if len(compact) <= limit:
            return compact
        return compact[: limit - 1].rstrip() + "…"

    @staticmethod
    def _top_key(counts: object) -> str:
        options = counts if isinstance(counts, dict) else {}
        return sorted(options.items(), key=lambda item: (-item[1], item[0]))[0][0] if options else "concept"

    def find_entities_by_label(
        self, kb_id: str, terms: list[str], limit: int = 8,
    ) -> list[str]:
        """Return canonical entity_ids whose labels contain any of the given terms."""
        if not terms:
            return []
        like_clauses = " OR ".join(["label LIKE ?" for _ in terms])
        params: list[object] = [kb_id] + [f"%{t}%" for t in terms] + [limit]
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT entity_id, COUNT(*) AS mention_count
                FROM entity_mentions
                WHERE kb_id = ? AND ({like_clauses})
                GROUP BY entity_id
                ORDER BY mention_count DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [str(row["entity_id"]) for row in rows]

    def get_neighbor_labels(
        self, kb_id: str, entity_ids: list[str], limit: int = 12,
    ) -> list[str]:
        """Return distinct labels of entities adjacent to the given entities."""
        if not entity_ids:
            return []
        placeholders = ", ".join("?" for _ in entity_ids)
        params: list[object] = [kb_id] + entity_ids + [kb_id] + entity_ids + [limit]
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT e.label, COUNT(*) AS edge_count
                FROM relation_mentions r
                JOIN entity_mentions e ON e.kb_id = r.kb_id AND e.entity_id = r.target_id
                WHERE r.kb_id = ? AND r.source_id IN ({placeholders})
                GROUP BY e.label
                UNION
                SELECT e.label, COUNT(*) AS edge_count
                FROM relation_mentions r
                JOIN entity_mentions e ON e.kb_id = r.kb_id AND e.entity_id = r.source_id
                WHERE r.kb_id = ? AND r.target_id IN ({placeholders})
                GROUP BY e.label
                ORDER BY edge_count DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [str(row["label"]) for row in rows]

    def get_chunk_candidates_for_entities(
        self, kb_id: str, entity_ids: list[str], limit: int = 24,
    ) -> list[dict[str, object]]:
        """Return chunk candidates with entity/relation mention stats."""
        if not entity_ids:
            return []
        placeholders = ", ".join("?" for _ in entity_ids)
        params: list[object] = [kb_id] + entity_ids + [kb_id] + entity_ids + entity_ids
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT chunk_id,
                       COUNT(*) AS entity_count,
                       0 AS relation_count,
                       COALESCE(SUM(confidence), 0.0) AS confidence_sum
                FROM entity_mentions
                WHERE kb_id = ? AND entity_id IN ({placeholders})
                GROUP BY chunk_id
                UNION ALL
                SELECT chunk_id,
                       0 AS entity_count,
                       COUNT(*) AS relation_count,
                       COALESCE(SUM(confidence), 0.0) AS confidence_sum
                FROM relation_mentions
                WHERE kb_id = ? AND (source_id IN ({placeholders}) OR target_id IN ({placeholders}))
                GROUP BY chunk_id
                ORDER BY (entity_count + relation_count) DESC
                """,
                params,
            ).fetchall()
        results: dict[str, dict[str, object]] = {}
        for row in rows:
            chunk_id = str(row["chunk_id"])
            if chunk_id not in results:
                results[chunk_id] = {"chunk_id": chunk_id, "entity_count": 0, "relation_count": 0, "confidence_sum": 0.0}
            bucket = results[chunk_id]
            bucket["entity_count"] = int(bucket["entity_count"]) + int(row["entity_count"])
            bucket["relation_count"] = int(bucket["relation_count"]) + int(row["relation_count"])
            bucket["confidence_sum"] = float(bucket["confidence_sum"]) + float(row["confidence_sum"])
        aggregated = sorted(results.values(), key=lambda x: (int(x["entity_count"]) + int(x["relation_count"])), reverse=True)
        return aggregated[:limit]

    def get_chunks_for_entity_set(
        self, kb_id: str, entity_ids: list[str], limit: int = 48,
    ) -> list[str]:
        """Return distinct chunk_ids for the given entities, ordered by relevance."""
        candidates = self.get_chunk_candidates_for_entities(kb_id, entity_ids, limit=limit)
        return [str(c["chunk_id"]) for c in candidates]