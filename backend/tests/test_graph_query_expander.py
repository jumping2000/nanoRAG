"""Tests for GraphQueryExpander."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from retrieval.graph_query_expander import GraphQueryExpander


class _FakeGraphStore:
    def __init__(self, db_path: Path) -> None:
        self.path = db_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
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

    def find_entities_by_label(self, kb_id, terms, limit=8):
        if not terms:
            return []
        clauses = " OR ".join(["label LIKE ?" for _ in terms])
        params = [kb_id] + [f"%{t}%" for t in terms] + [limit]
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT entity_id, COUNT(*) AS c FROM entity_mentions "
                f"WHERE kb_id = ? AND ({clauses}) GROUP BY entity_id ORDER BY c DESC LIMIT ?",
                params,
            ).fetchall()
        return [r["entity_id"] for r in rows]

    def get_neighbor_labels(self, kb_id, entity_ids, limit=12):
        if not entity_ids:
            return []
        ph = ", ".join("?" for _ in entity_ids)
        params = [kb_id] + entity_ids + [kb_id] + entity_ids + [limit]
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT label, SUM(cnt) AS total FROM ("
                f"SELECT e.label, COUNT(*) AS cnt FROM relation_mentions r "
                f"JOIN entity_mentions e ON e.entity_id = r.target_id "
                f"WHERE r.kb_id = ? AND r.source_id IN ({ph}) GROUP BY e.label "
                f"UNION ALL "
                f"SELECT e.label, COUNT(*) AS cnt FROM relation_mentions r "
                f"JOIN entity_mentions e ON e.entity_id = r.source_id "
                f"WHERE r.kb_id = ? AND r.target_id IN ({ph}) GROUP BY e.label"
                f") GROUP BY label ORDER BY total DESC LIMIT ?",
                params,
            ).fetchall()
        return [r["label"] for r in rows]


@pytest.fixture
def expander(tmp_path):
    db = tmp_path / "test.db"
    store = _FakeGraphStore(db)
    return GraphQueryExpander(store, max_terms=4)


def test_no_match_returns_original_query(expander):
    result = expander.expand("test-kb", "what is machine learning")
    assert result.expanded_query == "what is machine learning"
    assert result.matched_entities == []
    assert result.added_terms == []


def test_empty_query_returns_original(expander):
    result = expander.expand("test-kb", "")
    assert result.expanded_query == ""
    assert result.added_terms == []


def test_alias_match_expands_with_canonical_label(tmp_path):
    db = tmp_path / "test.db"
    store = _FakeGraphStore(db)
    with store._connect() as conn:
        conn.execute("INSERT INTO entity_mentions VALUES (?,?,?,?,?,?)", ("kb1", "soa", "SOA", "concept", 0.9, "c1"))
        conn.execute("INSERT INTO entity_mentions VALUES (?,?,?,?,?,?)", ("kb1", "soa", "Service Oriented Architecture", "concept", 0.8, "c2"))
        conn.execute("INSERT INTO entity_mentions VALUES (?,?,?,?,?,?)", ("kb1", "esb", "Enterprise Service Bus", "concept", 0.9, "c3"))
        conn.execute("INSERT INTO relation_mentions VALUES (?,?,?,?,?,?)", ("kb1", "soa", "esb", "uses", 0.8, "c3"))
    e = GraphQueryExpander(store, max_terms=4)
    result = e.expand("kb1", "what is SOA")
    assert "soa" in result.added_terms or len(result.matched_entities) > 0
    assert result.expanded_query != "what is SOA"


def test_cap_max_terms_respected(tmp_path):
    db = tmp_path / "test.db"
    store = _FakeGraphStore(db)
    with store._connect() as conn:
        for i in range(6):
            conn.execute("INSERT INTO entity_mentions VALUES (?,?,?,?,?,?)", ("kb1", f"e{i}", f"Term{i}", "concept", 0.9, "c1"))
            conn.execute("INSERT INTO relation_mentions VALUES (?,?,?,?,?,?)", ("kb1", "e0", f"e{i}", "related_to", 0.5, "c1"))
    e = GraphQueryExpander(store, max_terms=3)
    result = e.expand("kb1", "Term0")
    assert len(result.added_terms) <= 3
