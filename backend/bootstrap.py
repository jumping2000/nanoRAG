from __future__ import annotations

from dataclasses import dataclass

from chunking.structural_chunker import StructuralChunker
from config import Settings
from providers.embedding_provider import EmbeddingProvider
from rag.catalog import MetadataCatalog
from rag.graph_extractor import GraphExtractor
from rag.graph_store import GraphStore
from rag.ingest import IngestionService
from retrieval.dense_search import DenseRetriever
from retrieval.sparse_search import SparseRetriever


@dataclass(slots=True, frozen=True)
class IngestionRuntime:
    embedding_provider: EmbeddingProvider
    dense_retriever: DenseRetriever
    sparse_retriever: SparseRetriever
    chunker: StructuralChunker
    catalog: MetadataCatalog
    graph_extractor: GraphExtractor
    graph_store: GraphStore
    ingestion_service: IngestionService


def build_ingestion_runtime(settings: Settings) -> IngestionRuntime:
    embedding_provider = EmbeddingProvider(settings)
    dense_retriever = DenseRetriever(settings, embedding_provider)
    sparse_retriever = SparseRetriever(settings)
    chunker = StructuralChunker(settings.chunk_size_tokens, settings.chunk_overlap_tokens)
    catalog = MetadataCatalog(settings)
    graph_extractor = GraphExtractor()
    graph_store = GraphStore(settings)
    ingestion_service = IngestionService(
        settings,
        chunker,
        dense_retriever,
        sparse_retriever,
        catalog,
        graph_extractor,
        graph_store,
    )
    return IngestionRuntime(
        embedding_provider=embedding_provider,
        dense_retriever=dense_retriever,
        sparse_retriever=sparse_retriever,
        chunker=chunker,
        catalog=catalog,
        graph_extractor=graph_extractor,
        graph_store=graph_store,
        ingestion_service=ingestion_service,
    )