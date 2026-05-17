from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from config import Settings, get_settings
from models import ChunkMetadata
from rag.graph_extractor import GraphExtractor
from rag.structured_graph_extractor import StructuredGraphExtractor


@dataclass(slots=True, frozen=True)
class ExtractorChunkResult:
    chunk_id: str
    entity_count: int
    relation_count: int
    failed: bool = False
    error: str | None = None


@dataclass(slots=True, frozen=True)
class ExtractorRunSummary:
    name: str
    chunks: int
    failed_chunks: int
    entity_mentions: int
    relation_mentions: int
    unique_entities: int
    unique_relations: int
    predicates: dict[str, int]


@dataclass(slots=True, frozen=True)
class ExtractorChunkDelta:
    chunk_id: str
    baseline_entities: int
    candidate_entities: int
    baseline_relations: int
    candidate_relations: int
    candidate_failed: bool
    candidate_error: str | None = None


@dataclass(slots=True, frozen=True)
class ExtractorBenchmark:
    fixture_path: str
    baseline: ExtractorRunSummary
    candidate: ExtractorRunSummary
    deltas: list[ExtractorChunkDelta]


def load_benchmark_chunks(fixture_path: Path) -> list[ChunkMetadata]:
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    return [ChunkMetadata.model_validate(item) for item in payload]


def compare_extractors(
    fixture_path: Path,
    baseline_extractor,
    candidate_extractor,
) -> ExtractorBenchmark:
    chunks = load_benchmark_chunks(fixture_path)
    baseline_summary, baseline_chunks = _run_extractor("heuristic", chunks, baseline_extractor)
    candidate_summary, candidate_chunks = _run_extractor("structured", chunks, candidate_extractor)
    baseline_map = {item.chunk_id: item for item in baseline_chunks}
    candidate_map = {item.chunk_id: item for item in candidate_chunks}

    deltas = [
        ExtractorChunkDelta(
            chunk_id=chunk.chunk_id,
            baseline_entities=baseline_map[chunk.chunk_id].entity_count,
            candidate_entities=candidate_map[chunk.chunk_id].entity_count,
            baseline_relations=baseline_map[chunk.chunk_id].relation_count,
            candidate_relations=candidate_map[chunk.chunk_id].relation_count,
            candidate_failed=candidate_map[chunk.chunk_id].failed,
            candidate_error=candidate_map[chunk.chunk_id].error,
        )
        for chunk in chunks
    ]
    return ExtractorBenchmark(
        fixture_path=str(fixture_path),
        baseline=baseline_summary,
        candidate=candidate_summary,
        deltas=deltas,
    )


def benchmark_default_extractors(settings: Settings, fixture_path: Path) -> ExtractorBenchmark:
    return compare_extractors(
        fixture_path=fixture_path,
        baseline_extractor=GraphExtractor(),
        candidate_extractor=StructuredGraphExtractor(settings),
    )


def _run_extractor(name: str, chunks: list[ChunkMetadata], extractor) -> tuple[ExtractorRunSummary, list[ExtractorChunkResult]]:
    failed_chunks = 0
    entity_mentions = 0
    relation_mentions = 0
    unique_entities: set[str] = set()
    unique_relations: set[tuple[str, str, str]] = set()
    predicates: Counter[str] = Counter()
    chunk_results: list[ExtractorChunkResult] = []

    for chunk in chunks:
        try:
            entities, relations = extractor.extract(chunk)
        except Exception as error:
            failed_chunks += 1
            chunk_results.append(
                ExtractorChunkResult(
                    chunk_id=chunk.chunk_id,
                    entity_count=0,
                    relation_count=0,
                    failed=True,
                    error=type(error).__name__,
                )
            )
            continue

        entity_mentions += len(entities)
        relation_mentions += len(relations)
        unique_entities.update(entity.canonical_id for entity in entities)
        unique_relations.update(
            (relation.source.canonical_id, relation.predicate, relation.target.canonical_id)
            for relation in relations
        )
        predicates.update(relation.predicate for relation in relations)
        chunk_results.append(
            ExtractorChunkResult(
                chunk_id=chunk.chunk_id,
                entity_count=len(entities),
                relation_count=len(relations),
            )
        )

    summary = ExtractorRunSummary(
        name=name,
        chunks=len(chunks),
        failed_chunks=failed_chunks,
        entity_mentions=entity_mentions,
        relation_mentions=relation_mentions,
        unique_entities=len(unique_entities),
        unique_relations=len(unique_relations),
        predicates=dict(sorted(predicates.items())),
    )
    return summary, chunk_results


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare heuristic and structured graph extractors")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("tests/fixtures/graph_benchmark_chunks.json"),
        help="Path to the benchmark chunk fixture JSON file",
    )
    args = parser.parse_args()
    benchmark = benchmark_default_extractors(get_settings(), args.fixture)
    print(json.dumps(asdict(benchmark), indent=2))


if __name__ == "__main__":
    main()