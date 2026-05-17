from __future__ import annotations

from agno.models.ollama import Ollama
from agno.models.openai import OpenAIChat

from config import Settings


def build_llm_model(
    settings: Settings,
    provider: str | None = None,
    model_id: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
):
    selected_provider = (provider or settings.llm_provider).strip().lower()
    selected_model = (model_id or settings.llm_model).strip()
    selected_api_key = api_key if api_key is not None else settings.llm_api_key
    selected_base_url = base_url if base_url is not None else settings.llm_base_url

    if selected_provider == "ollama":
        return Ollama(
            id=selected_model,
            host=settings.ollama_host,
            timeout=120.0,
        )

    return OpenAIChat(
        id=selected_model,
        api_key=selected_api_key or "local",
        base_url=selected_base_url,
        timeout=120.0,
    )
