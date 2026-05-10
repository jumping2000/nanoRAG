from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _csv_env(name: str, default: str) -> tuple[str, ...]:
    raw = os.getenv(name, default)
    return tuple(part.strip() for part in raw.split(",") if part.strip())


@dataclass(slots=True, frozen=True)
class Settings:
    app_name: str
    environment: str
    llm_provider: str
    llm_api_key: str | None
    llm_base_url: str | None
    llm_model: str
    embedding_provider: str
    embedding_api_key: str | None
    embedding_base_url: str | None
    embedding_model: str
    ollama_host: str
    qdrant_url: str
    qdrant_api_key: str | None
    qdrant_collection: str
    retrieval_top_k: int
    chunk_size_tokens: int
    chunk_overlap_tokens: int
    cors_origins: tuple[str, ...]
    data_dir: Path
    uploads_dir: Path
    chunks_store_path: Path
    prompt_path: Path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    data_dir = BASE_DIR / "data"
    uploads_dir = data_dir / "uploads"
    data_dir.mkdir(parents=True, exist_ok=True)
    uploads_dir.mkdir(parents=True, exist_ok=True)

    llm_provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", llm_provider).strip().lower()

    llm_base_url = os.getenv("LLM_BASE_URL")
    if not llm_base_url and llm_provider == "openrouter":
        llm_base_url = "https://openrouter.ai/api/v1"

    embedding_base_url = os.getenv("EMBEDDING_BASE_URL")
    if not embedding_base_url and embedding_provider == "openrouter":
        embedding_base_url = "https://openrouter.ai/api/v1"
    if not embedding_base_url and embedding_provider == "openai":
        embedding_base_url = llm_base_url

    return Settings(
        app_name="nanoRAG",
        environment=os.getenv("APP_ENV", "development"),
        llm_provider=llm_provider,
        llm_api_key=os.getenv("LLM_API_KEY"),
        llm_base_url=llm_base_url,
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        embedding_provider=embedding_provider,
        embedding_api_key=os.getenv("EMBEDDING_API_KEY") or os.getenv("LLM_API_KEY"),
        embedding_base_url=embedding_base_url,
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY"),
        qdrant_collection=os.getenv("QDRANT_COLLECTION", "nanorag_chunks"),
        retrieval_top_k=int(os.getenv("RETRIEVAL_TOP_K", "6")),
        chunk_size_tokens=int(os.getenv("CHUNK_SIZE_TOKENS", "450")),
        chunk_overlap_tokens=int(os.getenv("CHUNK_OVERLAP_TOKENS", "80")),
        cors_origins=_csv_env(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,http://frontend:3000",
        ),
        data_dir=data_dir,
        uploads_dir=uploads_dir,
        chunks_store_path=data_dir / "chunks.jsonl",
        prompt_path=BASE_DIR / "prompts" / "system.md",
    )
