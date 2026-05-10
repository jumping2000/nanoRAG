from __future__ import annotations

from typing import Sequence

import httpx


class OllamaEmbeddingClient:
    def __init__(self, host: str, model: str, timeout: float = 120.0) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        response = httpx.post(
            f"{self.host}/api/embed",
            json={"model": self.model, "input": list(texts)},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        if "embeddings" in payload:
            return payload["embeddings"]
        if "embedding" in payload:
            return [payload["embedding"]]

        raise ValueError("Unexpected Ollama embeddings response format")
