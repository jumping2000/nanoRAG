from __future__ import annotations

import sqlite3
from pathlib import Path

from config import Settings
from models import (
    ChunkMetadata,
    ExtractedEntity,
    ExtractedRelation,
    GraphEdge,
    GraphEvidence,
    GraphNode,
    GraphSnapshot,
    GraphStats,
)


class GraphStore:
    def __init__(self, settings: Settings) -> None:
        self.path = Path(settings.graph_store_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def replace_chunk(
        self,
        chunk: ChunkMetadata,
        entities: list[ExtractedEntity],
        relations: list[ExtractedRelation],
    ) -> None:
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

    def delete_document(self, kb_id: str, document_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM entity_mentions WHERE kb_id = ? AND document_id = ?",
                (kb_id, document_id),
            )
            connection.execute(
                "DELETE FROM relation_mentions WHERE kb_id = ? AND document_id = ?",
                (kb_id, document_id),
            )

    def delete_kb(self, kb_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM entity_mentions WHERE kb_id = ?", (kb_id,))
            connection.execute("DELETE FROM relation_mentions WHERE kb_id = ?", (kb_id,))

    def get_snapshot(self, kb_id: str, limit: int = 18, min_weight: int = 1) -> GraphSnapshot:
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

        return GraphSnapshot(
            kb_id=kb_id,
            nodes=nodes,
            edges=sorted_edges,
            stats=GraphStats(
                nodes=len(nodes),
                edges=len(sorted_edges),
                mentions=len(entity_rows),
            ),
        )

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
                CREATE INDEX IF NOT EXISTS idx_entity_mentions_document ON entity_mentions (kb_id, document_id);
                CREATE INDEX IF NOT EXISTS idx_relation_mentions_kb ON relation_mentions (kb_id);
                CREATE INDEX IF NOT EXISTS idx_relation_mentions_document ON relation_mentions (kb_id, document_id);
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