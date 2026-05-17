from __future__ import annotations

import json
import logging
import re
import time

from agno.agent import Agent
from pydantic import BaseModel

from config import Settings
from observability import observe
from providers.llm_provider import build_llm_model

JSON_PATTERN = re.compile(r"\{.*\}", re.DOTALL)
WHITESPACE_PATTERN = re.compile(r"\s+")
logger = logging.getLogger(__name__)


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
        started = time.perf_counter()

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
                observe(
                    logger,
                    logging.WARNING,
                    "orchestrator",
                    "plan.fallback",
                    reason="missing_json",
                    message_length=len(message),
                    elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
                )
                return fallback
            payload = json.loads(matched.group(0))
            plan = RetrievalPlan(
                original_query=message,
                search_query=str(payload.get("search_query") or fallback.search_query).strip(),
                needs_retrieval=bool(payload.get("needs_retrieval", True)),
                answer_style=str(payload.get("answer_style") or "grounded"),
            )
            observe(
                logger,
                logging.INFO,
                "orchestrator",
                "plan.generated",
                search_query=plan.search_query,
                needs_retrieval=plan.needs_retrieval,
                answer_style=plan.answer_style,
                message_length=len(message),
                elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            return plan
        except Exception as error:
            observe(
                logger,
                logging.WARNING,
                "orchestrator",
                "plan.fallback",
                reason=type(error).__name__,
                message_length=len(message),
                elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            return fallback

    def _fallback_plan(self, message: str) -> RetrievalPlan:
        normalized = WHITESPACE_PATTERN.sub(" ", message).strip()
        return RetrievalPlan(
            original_query=message,
            search_query=normalized,
            needs_retrieval=True,
            answer_style="grounded",
        )
