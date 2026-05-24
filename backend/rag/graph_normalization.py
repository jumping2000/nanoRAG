from __future__ import annotations

import re

from models import GRAPH_PREDICATES

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
SEPARATOR_PATTERN = re.compile(r"[^a-z0-9]+")
KNOWN_ENTITY_ALIASES = {
    "i-b-m": "ibm",
}


def canonicalize_entity_label(label: str) -> str:
    tokens = TOKEN_PATTERN.findall(label.strip().lower())
    if not tokens:
        return "entity"

    if len(tokens) > 1 and all(len(token) == 1 for token in tokens):
        normalized = "".join(tokens)
    else:
        normalized = "-".join(tokens)

    return merge_known_aliases(normalized)


def normalize_predicate(predicate: str) -> str:
    normalized = SEPARATOR_PATTERN.sub("_", predicate.strip().lower()).strip("_")
    if normalized in GRAPH_PREDICATES:
        return normalized
    return "related_to"


def merge_known_aliases(entity_id: str) -> str:
    return KNOWN_ENTITY_ALIASES.get(entity_id, entity_id)