"""Graph-aware query expansion — appends entity labels from the knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ExpandedQuery:
    original_query: str
    expanded_query: str
    matched_entities: list[str]
    added_terms: list[str]


class GraphQueryExpander:
    def __init__(self, graph_store, max_terms: int = 4) -> None:
        self._graph_store = graph_store
        self._max_terms = max_terms

    def expand(self, kb_id: str, query: str) -> ExpandedQuery:
        tokens = [t.lower() for t in query.split() if len(t) > 2]
        if not tokens:
            return ExpandedQuery(
                original_query=query,
                expanded_query=query,
                matched_entities=[],
                added_terms=[],
            )

        matched = self._graph_store.find_entities_by_label(kb_id, tokens, limit=8)
        if not matched:
            return ExpandedQuery(
                original_query=query,
                expanded_query=query,
                matched_entities=[],
                added_terms=[],
            )

        neighbor_labels = self._graph_store.get_neighbor_labels(
            kb_id, matched, limit=self._max_terms * 2,
        )

        added: list[str] = []
        for label in neighbor_labels:
            normalized = label.strip().lower()
            if normalized and normalized not in query.lower() and normalized not in added:
                added.append(normalized)
            if len(added) >= self._max_terms:
                break

        expanded = query
        if added:
            expanded = f"{query} {' '.join(added)}"

        return ExpandedQuery(
            original_query=query,
            expanded_query=expanded,
            matched_entities=matched,
            added_terms=added,
        )
