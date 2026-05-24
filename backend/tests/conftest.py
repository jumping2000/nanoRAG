import os

import pytest

from config import get_settings

CONFIG_ENV_VARS = (
    "APP_ENV",
    "LLM_PROVIDER",
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "GRAPH_EXTRACTION_ENABLED",
    "GRAPH_EXTRACTION_PROVIDER",
    "GRAPH_EXTRACTION_API_KEY",
    "GRAPH_EXTRACTION_BASE_URL",
    "GRAPH_EXTRACTION_MODEL",
    "GRAPH_EXTRACTION_MAX_CHUNKS_PER_DOCUMENT",
    "GRAPH_EXTRACTION_MIN_CONFIDENCE",
    "EMBEDDING_PROVIDER",
    "EMBEDDING_API_KEY",
    "EMBEDDING_BASE_URL",
    "EMBEDDING_MODEL",
    "OLLAMA_HOST",
    "QDRANT_URL",
    "QDRANT_API_KEY",
    "QDRANT_COLLECTION",
    "RETRIEVAL_TOP_K",
    "CHUNK_SIZE_TOKENS",
    "CHUNK_OVERLAP_TOKENS",
    "CORS_ORIGINS",
)


@pytest.fixture(autouse=True)
def clear_settings_cache():
    original_values = {name: os.environ.get(name) for name in CONFIG_ENV_VARS}
    for name in CONFIG_ENV_VARS:
        os.environ.pop(name, None)
    get_settings.cache_clear()
    yield
    for name, value in original_values.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    get_settings.cache_clear()