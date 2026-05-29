"""Tests for GraphRetriever."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from models import ChunkMetadata
from retrieval.graph_search import GraphRetriever


class _FakeGraphStore:
    def __init__(self, db_path: Path) -> None:
        self.path = db_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.path)) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS entity_mentions (
                    kb_id TEXT, entity_id TEXT, label TEXT,
                    entity_type TEXT, confidence REAL, chunk_id TEXT
                );
                CREATE TABLE IF NOT EXISTS relation_mentions (
                    kb_id TEXT, source_id TEXT, target_id TEXT,
                    predicate TEXT, confidence REAL, chunk_id TEXT
                );
            """)

    def get_chunk_candidates_for_entities(self, kb_id, entity_ids, limit=24):
        if not entity_ids:
            return []
        ph = ",".join("?" for _ in entity_ids)
        params = [kb_id] + entity_ids + [kb_id] + entity_ids + entity_ids
        with sqlite3.connect(str(self.path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""SELECT chunk_id, COUNT(*) AS entity_count, 0 AS relation_count, COALESCE(SUM(confidence),0.0) AS confidence_sum
                FROM entity_mentions WHERE kb_id=? AND entity_id IN ({ph})
                GROUP BY chunk_id
                UNION ALL
                SELECT chunk_id, 0 AS entity_count, COUNT(*) AS relation_count, COALESCE(SUM(confidence),0.0) AS confidence_sum
                FROM relation_mentions WHERE kb_id=? AND (source_id IN ({ph}) OR target_id IN ({ph}))
                GROUP BY chunk_id""",
                params,
            ).fetchall()
        results = {}
        for row in rows:
            cid = row["chunk_id"]
            if cid not in results:
                results[cid] = {"chunk_id": cid, "entity_count": 0, "relation_count": 0, "confidence_sum": 0.0}
            results[cid]["entity_count"] += row["entity_count"]
            results[cid]["relation_count"] += row["relation_count"]
            results[cid]["confidence_sum"] += row["confidence_sum"]
        return sorted(results.values(), key=lambda x: x["entity_count"] + x["relation_count"], reverse=True)[:limit]


class _FakeSparse:
    def list_chunks(self, kb_id):
        return [
            ChunkMetadata(chunk_id="c1", kb_id=kb_id, kb_name=kb_id, document_id="d1", source="test", filename="f1.pdf", page=1, section="s1", text="chunk one", token_count=0),
            ChunkMetadata(chunk_id="c2", kb_id=kb_id, kb_name=kb_id, document_id="d2", source="test", filename="f2.pdf", page=1, section="s1", text="chunk two", token_count=0),
        ]


@pytest.fixture
def retriever(tmp_path):
    store = _FakeGraphStore(tmp_path / "test.db")
    return GraphRetriever(store, _FakeSparse())


def test_empty_seeds_returns_empty(retriever):
    result = retriever.search("kb1", [], top_k=6)
    assert result == []


def test_entity_match_returns_scored_candidates(tmp_path):
    store = _FakeGraphStore(tmp_path / "test.db")
    with sqlite3.connect(str(store.path)) as conn:
        conn.execute("INSERT INTO entity_mentions VALUES (?,?,?,?,?,?)", ("kb1", "entity-a", "EntityA", "concept", 0.9, "c1"))
        conn.execute("INSERT INTO entity_mentions VALUES (?,?,?,?,?,?)", ("kb1", "entity-a", "EntityA", "concept", 0.7, "c1"))
    ret = GraphRetriever(store, _FakeSparse())
    result = ret.search("kb1", ["entity-a"], top_k=6)
    assert len(result) == 1
    assert result[0].chunk_id == "c1"
    assert result[0].score > 0


def test_relation_chunks_score_above_entity_only(tmp_path):
    store = _FakeGraphStore(tmp_path / "test.db")
    with sqlite3.connect(str(store.path)) as conn:
        conn.execute("INSERT INTO entity_mentions VALUES (?,?,?,?,?,?)", ("kb1", "e1", "E1", "concept", 0.9, "c1"))
        conn.execute("INSERT INTO entity_mentions VALUES (?,?,?,?,?,?)", ("kb1", "e2", "E2", "concept", 0.9, "c2"))
        conn.execute("INSERT INTO relation_mentions VALUES (?,?,?,?,?,?)", ("kb1", "e1", "e2", "depends_on", 0.9, "c2"))
    ret = GraphRetriever(store, _FakeSparse())
    result = ret.search("kb1", ["e1", "e2"], top_k=6)
    assert len(result) == 2
    assert result[0].chunk_id == "c2"


def test_missing_chunk_metadata_dropped(tmp_path):
    store = _FakeGraphStore(tmp_path / "test.db")
    with sqlite3.connect(str(store.path)) as conn:
        conn.execute("INSERT INTO entity_mentions VALUES (?,?,?,?,?,?)", ("kb1", "e1", "E1", "concept", 0.9, "c-missing"))
    ret = GraphRetriever(store, _FakeSparse())
    result = ret.search("kb1", ["e1"], top_k=6)
    assert result == []
