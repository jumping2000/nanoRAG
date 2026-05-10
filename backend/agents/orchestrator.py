from __future__ import annotations

import json
import re

from agno.agent import Agent
from pydantic import BaseModel

from config import Settings
from providers.llm_provider import build_llm_model

JSON_PATTERN = re.compile(r"\{.*\}", re.DOTALL)
WHITESPACE_PATTERN = re.compile(r"\s+")


class RetrievalPlan(BaseModel):
    original_query: str
    search_query: str
    needs_retrieval: bool = True
    answer_style: str = "grounded"


class OrchestratorAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model = build_llm_model(settings)

    def plan(self, message: str) -> RetrievalPlan:
        fallback = self._fallback_plan(message)

        try:
            agent = Agent(
                model=self.model,
                markdown=False,
                telemetry=False,
                instructions=[
                    "You prepare retrieval plans for a grounded document assistant.",
                    "Always assume retrieval is needed unless the user explicitly asks for system status.",
                    "Respond with a single JSON object and no prose.",
                    'Use the keys: search_query, needs_retrieval, answer_style.',
                    "Keep search_query compact, preserve acronyms, codes and exact technical terms.",
                ],
            )
            response = agent.run(message)
            content = str(getattr(response, "content", "")).strip()
            matched = JSON_PATTERN.search(content)
            if not matched:
                return fallback
            payload = json.loads(matched.group(0))
            return RetrievalPlan(
                original_query=message,
                search_query=str(payload.get("search_query") or fallback.search_query).strip(),
                needs_retrieval=bool(payload.get("needs_retrieval", True)),
                answer_style=str(payload.get("answer_style") or "grounded"),
            )
        except Exception:
            return fallback

    def _fallback_plan(self, message: str) -> RetrievalPlan:
        normalized = WHITESPACE_PATTERN.sub(" ", message).strip()
        return RetrievalPlan(
            original_query=message,
            search_query=normalized,
            needs_retrieval=True,
            answer_style="grounded",
        )
