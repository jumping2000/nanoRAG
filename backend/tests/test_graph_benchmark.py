from pathlib import Path

from graph_benchmark import compare_extractors
from models import ExtractedEntity, ExtractedRelation


class StubExtractor:
    def __init__(self, responses):
        self.responses = responses

    def extract(self, chunk):
        response = self.responses[chunk.chunk_id]
        if isinstance(response, Exception):
            raise response
        return response


def _entity(label: str, canonical_id: str) -> ExtractedEntity:
    return ExtractedEntity(label=label, canonical_id=canonical_id, entity_type="concept", confidence=0.8)


def _relation(source: ExtractedEntity, predicate: str, target: ExtractedEntity) -> ExtractedRelation:
    return ExtractedRelation(source=source, target=target, predicate=predicate, confidence=0.8)


def test_compare_extractors_reports_counts_and_failures() -> None:
    fixture_path = Path("tests/fixtures/graph_benchmark_chunks.json")
    fastapi = _entity("FastAPI", "fastapi")
    qdrant = _entity("Qdrant", "qdrant")
    baseline = StubExtractor(
        {
            "arch-1": ([fastapi, qdrant], [_relation(fastapi, "uses", qdrant)]),
            "arch-2": ([qdrant], []),
        }
    )
    candidate = StubExtractor(
        {
            "arch-1": ([fastapi, qdrant], [_relation(fastapi, "uses", qdrant)]),
            "arch-2": RuntimeError("model failed"),
        }
    )

    benchmark = compare_extractors(fixture_path, baseline, candidate)

    assert benchmark.baseline.entity_mentions == 3
    assert benchmark.baseline.relation_mentions == 1
    assert benchmark.candidate.failed_chunks == 1
    assert benchmark.deltas[1].candidate_failed is True
    assert benchmark.deltas[1].candidate_error == "RuntimeError"