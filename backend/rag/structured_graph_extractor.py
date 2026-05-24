from __future__ import annotations

import json
import logging
import re

from agno.agent import Agent

from config import Settings
from models import (
    GRAPH_ENTITY_TYPES,
    GRAPH_PREDICATES,
    ChunkMetadata,
    ExtractedEntity,
    ExtractedRelation,
    GraphExtractionEntity,
    GraphExtractionRelation,
    GraphExtractionResult,
)
from observability import observe
from providers.llm_provider import build_llm_model
from rag.graph_extractor import GraphExtractor
from rag.graph_normalization import canonicalize_entity_label, normalize_predicate

FENCE_PATTERN = re.compile(r"```(?:json)?", re.IGNORECASE)
TRAILING_COMMA_PATTERN = re.compile(r",(\s*[}\]])")
SEPARATOR_PATTERN = re.compile(r"[^a-z0-9]+")
logger = logging.getLogger(__name__)


class StructuredGraphExtractor(GraphExtractor):
    def __init__(self, settings: Settings, fallback: GraphExtractor | None = None) -> None:
        self.settings = settings
        self.fallback = fallback
        self.prompt = settings.graph_extraction_prompt_path.read_text(encoding="utf-8")
        self.model = build_llm_model(
            settings,
            provider=settings.graph_extraction_provider,
            model_id=settings.graph_extraction_model,
            api_key=settings.graph_extraction_api_key,
            base_url=settings.graph_extraction_base_url,
        )

    def extract(self, chunk: ChunkMetadata) -> tuple[list[ExtractedEntity], list[ExtractedRelation]]:
        try:
            extraction = self._parse_response(self._run_prompt(chunk))
            entities = self._build_entities(extraction.entities)
            relations = self._build_relations(extraction.relations, entities)
            observe(
                logger,
                logging.DEBUG,
                "graph_extract",
                "structured.completed",
                kb_id=chunk.kb_id,
                chunk_id=chunk.chunk_id,
                entities=len(entities),
                relations=len(relations),
                fallback_used=False,
            )
            return entities, relations
        except Exception as error:
            observe(
                logger,
                logging.WARNING,
                "graph_extract",
                "structured.fallback",
                kb_id=chunk.kb_id,
                chunk_id=chunk.chunk_id,
                reason=type(error).__name__,
            )
            if self.fallback is None:
                raise
            return self.fallback.extract(chunk)

    def _run_prompt(self, chunk: ChunkMetadata) -> str:
        agent = Agent(
            model=self.model,
            markdown=False,
            telemetry=False,
            instructions=[self.prompt],
        )
        response = agent.run(self._build_prompt(chunk))
        return str(getattr(response, "content", "")).strip()

    def _build_prompt(self, chunk: ChunkMetadata) -> str:
        allowed_entity_types = ", ".join(GRAPH_ENTITY_TYPES)
        allowed_predicates = ", ".join(GRAPH_PREDICATES)
        return (
            f"Allowed entity types: {allowed_entity_types}\n"
            f"Allowed predicates: {allowed_predicates}\n\n"
            f"Filename: {chunk.filename}\n"
            f"Page: {chunk.page or '-'}\n"
            f"Section: {chunk.section or '-'}\n"
            f"Chunk text:\n{chunk.text}"
        )

    def _parse_response(self, content: str) -> GraphExtractionResult:
        payload = self._load_json_payload(content)
        return GraphExtractionResult.model_validate(self._sanitize_payload(payload))

    def _load_json_payload(self, content: str) -> dict[str, object]:
        normalized_content = FENCE_PATTERN.sub("", content).replace("“", '"').replace("”", '"').strip()
        decoder = json.JSONDecoder()

        for start in (index for index, char in enumerate(normalized_content) if char == "{"):
            candidate = normalized_content[start:]
            payload = self._decode_candidate(decoder, candidate)
            if isinstance(payload, dict) and ("entities" in payload or "relations" in payload):
                return payload

        raise ValueError("Graph extraction did not return a valid JSON object")

    def _decode_candidate(self, decoder: json.JSONDecoder, candidate: str) -> dict[str, object] | None:
        for attempt in (candidate, self._repair_json(candidate)):
            try:
                payload, _ = decoder.raw_decode(attempt)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        return None

    def _repair_json(self, candidate: str) -> str:
        return TRAILING_COMMA_PATTERN.sub(r"\1", candidate)

    def _sanitize_payload(self, payload: dict[str, object]) -> dict[str, object]:
        entities = payload.get("entities") if isinstance(payload.get("entities"), list) else []
        relations = payload.get("relations") if isinstance(payload.get("relations"), list) else []
        return {
            "entities": [entity for entity in (self._sanitize_entity(item) for item in entities) if entity],
            "relations": [relation for relation in (self._sanitize_relation(item) for item in relations) if relation],
        }

    def _sanitize_entity(self, item: object) -> dict[str, object] | None:
        if not isinstance(item, dict):
            return None

        label = self._coerce_text(item.get("label") or item.get("name") or item.get("entity"))
        if not label:
            return None

        return {
            "label": label,
            "entity_type": self._normalize_entity_type(item.get("entity_type") or item.get("type")),
            "confidence": self._coerce_confidence(item.get("confidence")),
        }

    def _sanitize_relation(self, item: object) -> dict[str, object] | None:
        if not isinstance(item, dict):
            return None

        source_label = self._coerce_label_field(item.get("source_label") or item.get("source"))
        target_label = self._coerce_label_field(item.get("target_label") or item.get("target"))
        if not source_label or not target_label:
            return None

        return {
            "source_label": source_label,
            "target_label": target_label,
            "predicate": normalize_predicate(
                self._coerce_text(item.get("predicate") or item.get("relation") or item.get("type"))
            ),
            "confidence": self._coerce_confidence(item.get("confidence")),
        }

    def _normalize_entity_type(self, value: object) -> str:
        normalized = SEPARATOR_PATTERN.sub("_", self._coerce_text(value).lower()).strip("_")
        if normalized in GRAPH_ENTITY_TYPES:
            return normalized

        alias_map = {
            "application": "system",
            "app": "system",
            "framework": "system",
            "platform": "system",
            "tool": "artifact",
            "library": "artifact",
            "document": "artifact",
            "vendor": "organization",
            "company": "organization",
            "team": "organization",
            "datastore": "database",
            "db": "database",
        }
        return alias_map.get(normalized, "other")

    def _coerce_label_field(self, value: object) -> str:
        if isinstance(value, dict):
            return self._coerce_text(value.get("label") or value.get("name") or value.get("id"))
        return self._coerce_text(value)

    def _coerce_text(self, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _coerce_confidence(self, value: object) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.0

        if confidence > 1.0 and confidence <= 100.0:
            confidence /= 100.0
        return min(1.0, max(0.0, confidence))

    def _build_entities(self, entities: list[GraphExtractionEntity]) -> list[ExtractedEntity]:
        materialized: list[ExtractedEntity] = []
        for entity in entities:
            if entity.confidence < self.settings.graph_extraction_min_confidence:
                continue
            materialized.append(
                ExtractedEntity(
                    label=entity.label.strip(),
                    canonical_id=canonicalize_entity_label(entity.label),
                    entity_type=entity.entity_type,
                    confidence=entity.confidence,
                )
            )
        return self._unique_entities(materialized)

    def _build_relations(
        self,
        relations: list[GraphExtractionRelation],
        entities: list[ExtractedEntity],
    ) -> list[ExtractedRelation]:
        if not entities:
            return []

        entities_by_label = {canonicalize_entity_label(entity.label): entity for entity in entities}
        materialized: list[ExtractedRelation] = []
        for relation in relations:
            if relation.confidence < self.settings.graph_extraction_min_confidence:
                continue

            source = entities_by_label.get(canonicalize_entity_label(relation.source_label))
            target = entities_by_label.get(canonicalize_entity_label(relation.target_label))
            if source is None or target is None or source.canonical_id == target.canonical_id:
                continue

            materialized.append(
                ExtractedRelation(
                    source=source,
                    target=target,
                    predicate=normalize_predicate(relation.predicate),
                    confidence=relation.confidence,
                )
            )

        return self._dedupe_relations(materialized)