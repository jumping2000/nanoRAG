from __future__ import annotations

import re
from pathlib import Path

from pydantic import ValidationError
from rank_bm25 import BM25Okapi

from config import Settings
from models import ChunkMetadata, RetrievedChunk

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_./:-]+")


class SparseRetriever:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._chunks_by_id: dict[str, ChunkMetadata] = {}
        self._ordered_chunks_by_kb: dict[str, list[ChunkMetadata]] = {}
        self._bm25_by_kb: dict[str, BM25Okapi] = {}
        self._load_store()

    def total_chunks(self, kb_id: str | None = None) -> int:
        if kb_id is None:
            return len(self._chunks_by_id)
        return len(self._ordered_chunks_by_kb.get(kb_id, []))

    def list_chunks(self, kb_id: str | None = None) -> list[ChunkMetadata]:
        if kb_id is None:
            return list(self._chunks_by_id.values())
        return list(self._ordered_chunks_by_kb.get(kb_id, []))

    def upsert(self, chunks: list[ChunkMetadata]) -> None:
        for chunk in chunks:
            self._chunks_by_id[chunk.chunk_id] = chunk
        self._persist_store()
        self._rebuild_index()

    def search(self, query: str, kb_id: str, top_k: int) -> list[RetrievedChunk]:
        bm25 = self._bm25_by_kb.get(kb_id)
        ordered_chunks = self._ordered_chunks_by_kb.get(kb_id, [])
        if bm25 is None or not ordered_chunks:
            return []

        tokens = self._tokenize(query)
        if not tokens:
            return []

        scores = bm25.get_scores(tokens)
        query_terms = set(tokens)
        overlap_scores = [
            len(query_terms.intersection(self._tokenize(chunk.text))) for chunk in ordered_chunks
        ]
        ranked = sorted(
            enumerate(scores),
            key=lambda item: (item[1], overlap_scores[item[0]]),
            reverse=True,
        )

        results: list[RetrievedChunk] = []
        for rank, (index, score) in enumerate(ranked, start=1):
            if len(results) >= top_k:
                break
            overlap_score = overlap_scores[index]
            if score <= 0 and overlap_score <= 0:
                continue
            chunk = ordered_chunks[index]
            results.append(
                RetrievedChunk(
                    **chunk.model_dump(),
                    score=float(max(score, float(overlap_score))),
                    rank=rank,
                ),
            )

        return results

    def delete_document(self, kb_id: str, document_id: str) -> None:
        self._chunks_by_id = {
            chunk_id: chunk
            for chunk_id, chunk in self._chunks_by_id.items()
            if not (chunk.kb_id == kb_id and chunk.document_id == document_id)
        }
        self._persist_store()
        self._rebuild_index()

    def delete_kb(self, kb_id: str) -> None:
        self._chunks_by_id = {
            chunk_id: chunk
            for chunk_id, chunk in self._chunks_by_id.items()
            if chunk.kb_id != kb_id
        }
        self._persist_store()
        self._rebuild_index()

    def _load_store(self) -> None:
        path = Path(self.settings.chunks_store_path)
        if not path.exists():
            return

        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                chunk = ChunkMetadata.model_validate_json(line)
            except ValidationError:
                continue
            self._chunks_by_id[chunk.chunk_id] = chunk

        self._rebuild_index()

    def _persist_store(self) -> None:
        path = Path(self.settings.chunks_store_path)
        serialized = "\n".join(
            chunk.model_dump_json()
            for chunk in self._chunks_by_id.values()
        )
        path.write_text(serialized, encoding="utf-8")

    def _rebuild_index(self) -> None:
        self._ordered_chunks_by_kb = {}
        self._bm25_by_kb = {}

        for chunk in self._chunks_by_id.values():
            self._ordered_chunks_by_kb.setdefault(chunk.kb_id, []).append(chunk)

        for kb_id, chunks in self._ordered_chunks_by_kb.items():
            tokenized_corpus = [self._tokenize(chunk.text) for chunk in chunks]
            if not tokenized_corpus:
                continue
            self._bm25_by_kb[kb_id] = BM25Okapi(tokenized_corpus)

    def _tokenize(self, text: str) -> list[str]:
        return [token.lower() for token in TOKEN_PATTERN.findall(text)]
