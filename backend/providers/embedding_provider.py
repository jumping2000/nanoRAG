from __future__ import annotations

import hashlib
from collections.abc import Sequence

from openai import OpenAI

from config import Settings
from providers.ollama import OllamaEmbeddingClient


class EmbeddingProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cache: dict[str, list[float]] = {}
        self._openai_client = None
        self._ollama_client = None

        if settings.embedding_provider == "ollama":
            self._ollama_client = OllamaEmbeddingClient(
                host=settings.ollama_host,
                model=settings.embedding_model,
            )
        else:
            self._openai_client = OpenAI(
                api_key=settings.embedding_api_key or "local",
                base_url=settings.embedding_base_url,
            )

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        normalized = [text.strip() for text in texts]
        if not normalized:
            return []

        results: list[list[float] | None] = [None] * len(normalized)
        missing: dict[str, dict[str, object]] = {}

        for index, text in enumerate(normalized):
            key = hashlib.sha1(text.encode("utf-8")).hexdigest()
            cached = self._cache.get(key)
            if cached is not None:
                results[index] = cached
                continue
            entry = missing.setdefault(key, {"text": text, "indexes": []})
            entry["indexes"].append(index)

        if missing:
            ordered_missing = list(missing.values())
            new_embeddings = self._request_embeddings(
                [entry["text"] for entry in ordered_missing],
            )
            for entry, embedding in zip(ordered_missing, new_embeddings, strict=True):
                key = hashlib.sha1(str(entry["text"]).encode("utf-8")).hexdigest()
                self._cache[key] = embedding
                for index in entry["indexes"]:
                    results[index] = embedding

        return [embedding for embedding in results if embedding is not None]

    def _request_embeddings(self, texts: Sequence[str]) -> list[list[float]]:
        if self._ollama_client is not None:
            return self._ollama_client.embed_texts(texts)

        assert self._openai_client is not None
        response = self._openai_client.embeddings.create(
            model=self.settings.embedding_model,
            input=list(texts),
        )
        return [item.embedding for item in response.data]
