from __future__ import annotations

import re
from collections.abc import Iterable

from models import ChunkMetadata, ExtractedEntity, ExtractedRelation
from rag.graph_normalization import canonicalize_entity_label

SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+|\n+")
TITLE_PHRASE_PATTERN = re.compile(
    r"\b(?:[A-Z][a-z0-9]+|[A-Z]{2,}[A-Z0-9./+-]*)(?:\s+(?:[A-Z][a-z0-9]+|[A-Z]{2,}[A-Z0-9./+-]*)){1,3}\b"
)
SINGLE_ENTITY_PATTERN = re.compile(
    r"\b(?:[A-Z]{2,}[A-Z0-9./+-]*|[A-Z][a-z0-9]{3,}|[A-Za-z0-9./+-]*[A-Z][A-Za-z0-9./+-]*[A-Z][A-Za-z0-9./+-]*)\b"
)

STOP_ENTITIES = {
    "Architecture",
    "Content",
    "Document",
    "Documents",
    "Graph",
    "Knowledge",
    "Overview",
    "Page",
    "Section",
    "Storage",
    "System",
    "This",
    "That",
    "These",
    "Those",
}

RELATION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("depends_on", re.compile(r"\bdepends on\b", re.IGNORECASE)),
    ("connects_to", re.compile(r"\bconnects to\b|\bconnected to\b", re.IGNORECASE)),
    ("uses", re.compile(r"\buses\b|\bused by\b", re.IGNORECASE)),
    ("stores", re.compile(r"\bstores\b|\bstored in\b", re.IGNORECASE)),
    ("indexes", re.compile(r"\bindexes\b|\bindexed in\b", re.IGNORECASE)),
    ("retrieves_from", re.compile(r"\bretrieves from\b|\breads from\b", re.IGNORECASE)),
    ("runs_on", re.compile(r"\bruns on\b", re.IGNORECASE)),
    ("belongs_to", re.compile(r"\bbelongs to\b", re.IGNORECASE)),
    ("manages", re.compile(r"\bmanages\b|\bmanaged by\b", re.IGNORECASE)),
    ("references", re.compile(r"\breferences\b|\breferred to as\b", re.IGNORECASE)),
)


class GraphExtractor:
    def extract(self, chunk: ChunkMetadata) -> tuple[list[ExtractedEntity], list[ExtractedRelation]]:
        entities_by_id: dict[str, ExtractedEntity] = {}
        relations: list[ExtractedRelation] = []

        for sentence in self._split_sentences(chunk.text):
            sentence_entities = self._extract_sentence_entities(sentence)
            for entity in sentence_entities:
                entities_by_id.setdefault(entity.canonical_id, entity)

            explicit_relations = self._extract_sentence_relations(sentence, sentence_entities)
            if explicit_relations:
                relations.extend(explicit_relations)
                continue

            unique_entities = self._unique_entities(sentence_entities)
            if 2 <= len(unique_entities) <= 3:
                for source, target in zip(unique_entities, unique_entities[1:]):
                    if source.canonical_id == target.canonical_id:
                        continue
                    relations.append(
                        ExtractedRelation(
                            source=source,
                            target=target,
                            predicate="related_to",
                            confidence=0.25,
                        )
                    )

        return list(entities_by_id.values()), self._dedupe_relations(relations)

    def _split_sentences(self, text: str) -> Iterable[str]:
        for part in SENTENCE_SPLIT_PATTERN.split(text):
            sentence = part.strip()
            if sentence:
                yield sentence

    def _extract_sentence_entities(self, sentence: str) -> list[ExtractedEntity]:
        matches: list[tuple[int, int, str]] = []
        for pattern in (TITLE_PHRASE_PATTERN, SINGLE_ENTITY_PATTERN):
            for match in pattern.finditer(sentence):
                label = match.group(0).strip(" .,:;()[]{}\"")
                if self._is_valid_entity(label):
                    matches.append((match.start(), match.end(), label))

        deduped: list[tuple[int, int, str]] = []
        seen_spans: set[tuple[int, int]] = set()
        for start, end, label in sorted(matches, key=lambda item: (item[0], -(item[1] - item[0]))):
            if any(start >= left and end <= right for left, right in seen_spans):
                continue
            deduped.append((start, end, label))
            seen_spans.add((start, end))

        entities: list[ExtractedEntity] = []
        for _, _, label in deduped:
            entities.append(
                ExtractedEntity(
                    label=label,
                    canonical_id=self.canonicalize_label(label),
                    entity_type=self._classify_entity(label),
                    confidence=0.55,
                )
            )
        return self._unique_entities(entities)

    def _extract_sentence_relations(
        self,
        sentence: str,
        entities: list[ExtractedEntity],
    ) -> list[ExtractedRelation]:
        if len(entities) < 2:
            return []

        ordered_positions: list[tuple[int, int, ExtractedEntity]] = []
        cursor = 0
        for entity in entities:
            index = sentence.find(entity.label, cursor)
            if index < 0:
                index = sentence.find(entity.label)
            if index < 0:
                continue
            ordered_positions.append((index, index + len(entity.label), entity))
            cursor = index + len(entity.label)

        relations: list[ExtractedRelation] = []
        for predicate, pattern in RELATION_PATTERNS:
            match = pattern.search(sentence)
            if not match:
                continue

            source = self._nearest_entity_before(ordered_positions, match.start())
            target = self._nearest_entity_after(ordered_positions, match.end())
            if not source or not target or source.canonical_id == target.canonical_id:
                continue

            relations.append(
                ExtractedRelation(
                    source=source,
                    target=target,
                    predicate=predicate,
                    confidence=0.75,
                )
            )

        return relations

    def _nearest_entity_before(
        self,
        ordered_positions: list[tuple[int, int, ExtractedEntity]],
        offset: int,
    ) -> ExtractedEntity | None:
        for start, end, entity in reversed(ordered_positions):
            if end <= offset:
                return entity
        return None

    def _nearest_entity_after(
        self,
        ordered_positions: list[tuple[int, int, ExtractedEntity]],
        offset: int,
    ) -> ExtractedEntity | None:
        for start, _, entity in ordered_positions:
            if start >= offset:
                return entity
        return None

    def _dedupe_relations(self, relations: list[ExtractedRelation]) -> list[ExtractedRelation]:
        deduped: dict[tuple[str, str, str], ExtractedRelation] = {}
        for relation in relations:
            key = (
                relation.source.canonical_id,
                relation.predicate,
                relation.target.canonical_id,
            )
            current = deduped.get(key)
            if current is None or relation.confidence > current.confidence:
                deduped[key] = relation
        return list(deduped.values())

    def _unique_entities(self, entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
        deduped: dict[str, ExtractedEntity] = {}
        for entity in entities:
            current = deduped.get(entity.canonical_id)
            if current is None or len(entity.label) > len(current.label):
                deduped[entity.canonical_id] = entity
        return list(deduped.values())

    def _is_valid_entity(self, label: str) -> bool:
        if label in STOP_ENTITIES:
            return False
        if label.isdigit():
            return False
        if len(label) < 3:
            return False
        if label.lower() == label:
            return False
        return True

    def _classify_entity(self, label: str) -> str:
        lowered = label.lower()
        if any(token in lowered for token in ("api", "service", "server", "gateway")):
            return "service"
        if any(token in lowered for token in ("db", "database", "qdrant", "postgres", "storage")):
            return "database"
        if any(token in lowered for token in ("framework", "fastapi", "next", "react", "agno", "ollama")):
            return "system"
        if label.isupper():
            return "organization"
        return "concept"

    @staticmethod
    def canonicalize_label(label: str) -> str:
        return canonicalize_entity_label(label)