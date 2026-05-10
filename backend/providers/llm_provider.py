from __future__ import annotations

from agno.models.ollama import Ollama
from agno.models.openai import OpenAIChat

from config import Settings


def build_llm_model(settings: Settings):
    if settings.llm_provider == "ollama":
        return Ollama(
            id=settings.llm_model,
            host=settings.ollama_host,
            timeout=120.0,
        )

    return OpenAIChat(
        id=settings.llm_model,
        api_key=settings.llm_api_key or "local",
        base_url=settings.llm_base_url,
        timeout=120.0,
    )
