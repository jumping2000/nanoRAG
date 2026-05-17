from __future__ import annotations

from collections.abc import Iterator, Sequence
import logging
import time

from agno.agent import Agent

from agents.orchestrator import RetrievalPlan
from config import Settings
from models import RetrievedChunk
from observability import observe
from providers.llm_provider import build_llm_model

logger = logging.getLogger(__name__)


class KnowledgeAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.system_prompt = settings.prompt_path.read_text(encoding="utf-8")

    def stream_answer(
        self,
        question: str,
        plan: RetrievalPlan,
        chunks: Sequence[RetrievedChunk],
    ) -> Iterator[str]:
        started = time.perf_counter()
        if not chunks:
            observe(
                logger,
                logging.WARNING,
                "knowledge",
                "stream.skipped",
                reason="no_chunks",
                question_length=len(question),
            )
            yield (
                "Non ho trovato contesto sufficiente nei documenti indicizzati. "
                "Carica fonti pertinenti oppure riformula la richiesta con termini piu specifici."
            )
            return

        agent = Agent(
            model=build_llm_model(self.settings),
            markdown=True,
            telemetry=False,
            instructions=[self.system_prompt],
        )
        prompt = self._build_prompt(question=question, plan=plan, chunks=chunks)
        observe(
            logger,
            logging.INFO,
            "knowledge",
            "stream.started",
            question_length=len(question),
            chunk_count=len(chunks),
            prompt_chars=len(prompt),
            answer_style=plan.answer_style,
        )
        emitted_tokens = 0
        try:
            run_stream = agent.run(prompt, stream=True)
            for event in run_stream:
                content = getattr(event, "content", None)
                if content:
                    emitted_tokens += 1
                    yield content
        finally:
            observe(
                logger,
                logging.INFO,
                "knowledge",
                "stream.completed",
                chunk_count=len(chunks),
                emitted_tokens=emitted_tokens,
                elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
            )

    def _build_prompt(
        self,
        question: str,
        plan: RetrievalPlan,
        chunks: Sequence[RetrievedChunk],
    ) -> str:
        formatted_context = "\n\n".join(
            (
                f"[S{index}] file={chunk.filename} page={chunk.page or '-'} "
                f"section={chunk.section or '-'}\n{chunk.text}"
            )
            for index, chunk in enumerate(chunks, start=1)
        )
        return (
            f"User question:\n{question}\n\n"
            f"Retrieval query:\n{plan.search_query}\n\n"
            f"Retrieved context:\n{formatted_context}\n\n"
            "Write a grounded Markdown answer using only the retrieved context."
        )
