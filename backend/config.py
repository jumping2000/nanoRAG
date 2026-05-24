from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
AppEnvironment = Literal["development", "production", "debug"]
WORKSPACE_ENV_PATH = BASE_DIR.parent / ".env"

load_dotenv(WORKSPACE_ENV_PATH, override=False)


def _csv_env(name: str, default: str) -> tuple[str, ...]:
    raw = os.getenv(name, default)
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default

    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _read_environment() -> AppEnvironment:
    value = os.getenv("APP_ENV", "development").strip().lower()
    if value in {"development", "production", "debug"}:
        return value
    raise ValueError(
        "APP_ENV must be one of development, production, debug"
    )


@dataclass(slots=True, frozen=True)
class Settings:
    app_name: str
    environment: AppEnvironment
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
    knowledge_bases_store_path: Path
    documents_store_path: Path
    graph_store_path: Path
    prompt_path: Path
    graph_extraction_enabled: bool
    graph_extraction_provider: str
    graph_extraction_api_key: str | None
    graph_extraction_base_url: str | None
    graph_extraction_model: str
    graph_extraction_max_chunks_per_document: int
    graph_extraction_min_confidence: float
    graph_extraction_prompt_path: Path

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_debug(self) -> bool:
        return self.environment == "debug"

    @property
    def enable_deep_observability(self) -> bool:
        return self.environment in {"development", "debug"}

    @property
    def enable_trace_details(self) -> bool:
        return self.environment == "debug"


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

    graph_extraction_provider = os.getenv("GRAPH_EXTRACTION_PROVIDER", llm_provider).strip().lower()
    graph_extraction_api_key = os.getenv("GRAPH_EXTRACTION_API_KEY")
    if not graph_extraction_api_key and graph_extraction_provider == llm_provider:
        graph_extraction_api_key = os.getenv("LLM_API_KEY")

    graph_extraction_base_url = os.getenv("GRAPH_EXTRACTION_BASE_URL")
    if not graph_extraction_base_url:
        if graph_extraction_provider == llm_provider:
            graph_extraction_base_url = llm_base_url
        elif graph_extraction_provider == "openrouter":
            graph_extraction_base_url = "https://openrouter.ai/api/v1"

    graph_extraction_model = os.getenv("GRAPH_EXTRACTION_MODEL", os.getenv("LLM_MODEL", "gpt-4o-mini")).strip()

    return Settings(
        app_name="nanoRAG",
        environment=_read_environment(),
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
        knowledge_bases_store_path=data_dir / "knowledge_bases.json",
        documents_store_path=data_dir / "documents.json",
        graph_store_path=data_dir / "knowledge_graph.db",
        prompt_path=BASE_DIR / "prompts" / "system.md",
        graph_extraction_enabled=_bool_env("GRAPH_EXTRACTION_ENABLED", False),
        graph_extraction_provider=graph_extraction_provider,
        graph_extraction_api_key=graph_extraction_api_key,
        graph_extraction_base_url=graph_extraction_base_url,
        graph_extraction_model=graph_extraction_model,
        graph_extraction_max_chunks_per_document=max(0, int(os.getenv("GRAPH_EXTRACTION_MAX_CHUNKS_PER_DOCUMENT", "24"))),
        graph_extraction_min_confidence=min(1.0, max(0.0, float(os.getenv("GRAPH_EXTRACTION_MIN_CONFIDENCE", "0.55")))),
        graph_extraction_prompt_path=BASE_DIR / "prompts" / "graph_extraction.md",
    )
