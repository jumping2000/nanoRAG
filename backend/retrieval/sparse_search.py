from __future__ import annotations

import re
from pathlib import Path

from rank_bm25 import BM25Okapi

from config import Settings
from models import ChunkMetadata, RetrievedChunk

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_./:-]+")


class SparseRetriever:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._chunks_by_id: dict[str, ChunkMetadata] = {}
        self._ordered_chunks: list[ChunkMetadata] = []
        self._bm25: BM25Okapi | None = None
        self._load_store()

    def total_chunks(self) -> int:
        return len(self._chunks_by_id)

    def upsert(self, chunks: list[ChunkMetadata]) -> None:
        for chunk in chunks:
            self._chunks_by_id[chunk.chunk_id] = chunk
        self._persist_store()
        self._rebuild_index()

    def search(self, query: str, top_k: int) -> list[RetrievedChunk]:
        if self._bm25 is None:
            return []

        tokens = self._tokenize(query)
        if not tokens:
            return []

        scores = self._bm25.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)

        results: list[RetrievedChunk] = []
        for rank, (index, score) in enumerate(ranked, start=1):
            if len(results) >= top_k:
                break
            if score <= 0:
                continue
            chunk = self._ordered_chunks[index]
            results.append(
                RetrievedChunk(
                    **chunk.model_dump(),
                    score=float(score),
                    rank=rank,
                ),
            )

        return results

    def _load_store(self) -> None:
        path = Path(self.settings.chunks_store_path)
        if not path.exists():
            return

        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            chunk = ChunkMetadata.model_validate_json(line)
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
        self._ordered_chunks = list(self._chunks_by_id.values())
        tokenized_corpus = [self._tokenize(chunk.text) for chunk in self._ordered_chunks]
        if not tokenized_corpus:
            self._bm25 = None
            return
        self._bm25 = BM25Okapi(tokenized_corpus)

    def _tokenize(self, text: str) -> list[str]:
        return [token.lower() for token in TOKEN_PATTERN.findall(text)]
