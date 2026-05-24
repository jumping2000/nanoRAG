import pytest

from config import get_settings
from models import ChunkMetadata
from providers import llm_provider
from rag.graph_extractor import GraphExtractor
from rag.graph_normalization import canonicalize_entity_label
from rag.structured_graph_extractor import StructuredGraphExtractor


class FallbackExtractor(GraphExtractor):
    def extract(self, chunk: ChunkMetadata):
        return super().extract(chunk)


def test_canonicalize_entity_label_merges_acronym_variants() -> None:
    assert canonicalize_entity_label("IBM") == "ibm"
    assert canonicalize_entity_label("I.B.M.") == "ibm"
    assert canonicalize_entity_label("Ibm") == "ibm"


def test_structured_graph_extractor_parses_valid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    object.__setattr__(settings, "graph_extraction_min_confidence", 0.6)

    monkeypatch.setattr(
        "rag.structured_graph_extractor.build_llm_model",
        lambda settings, provider=None, model_id=None, api_key=None, base_url=None: object(),
    )

    extractor = StructuredGraphExtractor(settings)
    monkeypatch.setattr(
        extractor,
        "_run_prompt",
        lambda chunk: (
            '{"entities":[{"label":"I.B.M.","entity_type":"organization","confidence":0.91},'
            '{"label":"Qdrant","entity_type":"database","confidence":0.88},'
            '{"label":"Noise","entity_type":"concept","confidence":0.2}],'
            '"relations":[{"source_label":"I.B.M.","target_label":"Qdrant","predicate":"uses","confidence":0.9},'
            '{"source_label":"Noise","target_label":"Qdrant","predicate":"references","confidence":0.3}]}'
        ),
    )

    chunk = ChunkMetadata(
        chunk_id="arch-1",
        kb_id="architecture",
        kb_name="Architecture",
        document_id="architecture-doc",
        source="kb:architecture/document:architecture-doc",
        filename="architecture.md",
        page=1,
        section="Overview",
        text="IBM uses Qdrant.",
        token_count=3,
    )

    entities, relations = extractor.extract(chunk)

    assert [entity.canonical_id for entity in entities] == ["ibm", "qdrant"]
    assert len(relations) == 1
    assert relations[0].predicate == "uses"
    assert relations[0].source.canonical_id == "ibm"
    assert relations[0].target.canonical_id == "qdrant"


def test_structured_graph_extractor_falls_back_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(
        "rag.structured_graph_extractor.build_llm_model",
        lambda settings, provider=None, model_id=None, api_key=None, base_url=None: object(),
    )

    extractor = StructuredGraphExtractor(settings, fallback=FallbackExtractor())
    monkeypatch.setattr(extractor, "_run_prompt", lambda chunk: "not-json")

    chunk = ChunkMetadata(
        chunk_id="arch-1",
        kb_id="architecture",
        kb_name="Architecture",
        document_id="architecture-doc",
        source="kb:architecture/document:architecture-doc",
        filename="architecture.md",
        page=1,
        section="Overview",
        text="FastAPI uses Qdrant for retrieval.",
        token_count=6,
    )

    entities, relations = extractor.extract(chunk)

    assert {entity.label for entity in entities} >= {"FastAPI", "Qdrant"}
    assert any(relation.predicate == "uses" for relation in relations)


def test_structured_graph_extractor_tolerates_fenced_json_trailing_commas_and_schema_variants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    object.__setattr__(settings, "graph_extraction_min_confidence", 0.6)

    monkeypatch.setattr(
        "rag.structured_graph_extractor.build_llm_model",
        lambda settings, provider=None, model_id=None, api_key=None, base_url=None: object(),
    )

    extractor = StructuredGraphExtractor(settings)
    monkeypatch.setattr(
        extractor,
        "_run_prompt",
        lambda chunk: (
            "Here is the extracted graph:\n"
            "```json\n"
            '{"entities":[{"label":"FastAPI","entity_type":"framework","confidence":"0.91"},'
            '{"label":"Qdrant","entity_type":"datastore","confidence":88},],'
            '"relations":[{"source":"FastAPI","target":"Qdrant","predicate":"runs-on","confidence":"0.74"},]}\n'
            "```"
        ),
    )

    chunk = ChunkMetadata(
        chunk_id="arch-2",
        kb_id="architecture",
        kb_name="Architecture",
        document_id="architecture-doc",
        source="kb:architecture/document:architecture-doc",
        filename="architecture.md",
        page=1,
        section="Overview",
        text="FastAPI runs on Qdrant.",
        token_count=4,
    )

    entities, relations = extractor.extract(chunk)

    assert [(entity.label, entity.entity_type) for entity in entities] == [
        ("FastAPI", "system"),
        ("Qdrant", "database"),
    ]
    assert len(relations) == 1
    assert relations[0].predicate == "runs_on"
    assert relations[0].confidence == pytest.approx(0.74)


def test_build_llm_model_uses_shared_provider_credentials_with_different_model(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class StubOpenAIChat:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm_provider, "OpenAIChat", StubOpenAIChat)
    settings = get_settings()
    object.__setattr__(settings, "llm_provider", "openrouter")
    object.__setattr__(settings, "llm_api_key", "shared-key")
    object.__setattr__(settings, "llm_base_url", "https://router.example/v1")

    llm_provider.build_llm_model(
        settings,
        provider="openrouter",
        model_id="graph-model",
        api_key="shared-key",
        base_url="https://router.example/v1",
    )

    assert captured["id"] == "graph-model"
    assert captured["api_key"] == "shared-key"
    assert captured["base_url"] == "https://router.example/v1"


def test_build_llm_model_uses_graph_specific_credentials_when_provider_differs(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class StubOpenAIChat:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm_provider, "OpenAIChat", StubOpenAIChat)
    settings = get_settings()
    object.__setattr__(settings, "llm_provider", "ollama")
    object.__setattr__(settings, "llm_api_key", None)
    object.__setattr__(settings, "llm_base_url", None)

    llm_provider.build_llm_model(
        settings,
        provider="openrouter",
        model_id="same-model-name",
        api_key="graph-key",
        base_url="https://openrouter.ai/api/v1",
    )

    assert captured["id"] == "same-model-name"
    assert captured["api_key"] == "graph-key"
    assert captured["base_url"] == "https://openrouter.ai/api/v1"