from __future__ import annotations

from io import BytesIO
from pathlib import Path
from datetime import UTC, datetime

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader

from chunking.structural_chunker import StructuralChunker
from config import Settings
from models import DocumentRecord, UploadResponse
from rag.catalog import MetadataCatalog
from rag.metadata import build_document_id
from retrieval.dense_search import DenseRetriever
from retrieval.sparse_search import SparseRetriever

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


class IngestionService:
    def __init__(
        self,
        settings: Settings,
        chunker: StructuralChunker,
        dense_retriever: DenseRetriever,
        sparse_retriever: SparseRetriever,
        catalog: MetadataCatalog,
    ) -> None:
        self.settings = settings
        self.chunker = chunker
        self.dense_retriever = dense_retriever
        self.sparse_retriever = sparse_retriever
        self.catalog = catalog

    async def ingest_upload(self, kb_id: str, upload: UploadFile) -> UploadResponse:
        kb = self.catalog.get_kb(kb_id)
        filename = Path(upload.filename or "document").name
        extension = Path(filename).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {extension}")

        content = await upload.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty upload")

        document_id = build_document_id(kb_id=kb.id, filename=filename, content=content)
        pages = self._extract_pages(extension, content)
        chunks = self.chunker.chunk_document(
            kb_id=kb.id,
            kb_name=kb.name,
            document_id=document_id,
            filename=filename,
            source=f"kb:{kb.id}/document:{document_id}",
            pages=pages,
        )

        self.dense_retriever.upsert(chunks)
        self.sparse_retriever.upsert(chunks)
        self.catalog.upsert_document(
            DocumentRecord(
                document_id=document_id,
                kb_id=kb.id,
                kb_name=kb.name,
                filename=filename,
                chunk_count=len(chunks),
                created_at=datetime.now(UTC).isoformat(),
            ),
        )

        return UploadResponse(
            document_id=document_id,
            filename=filename,
            ingested_chunks=len(chunks),
        )

    def indexed_chunks(self) -> int:
        return self.sparse_retriever.total_chunks()

    def list_documents(self, kb_id: str) -> list[DocumentRecord]:
        return self.catalog.list_documents(kb_id)

    def delete_document(self, kb_id: str, document_id: str) -> DocumentRecord:
        deleted = self.catalog.delete_document(kb_id, document_id)
        self.dense_retriever.delete_document(kb_id, document_id)
        self.sparse_retriever.delete_document(kb_id, document_id)
        return deleted

    def delete_kb(self, kb_id: str) -> None:
        self.catalog.delete_kb(kb_id)
        self.dense_retriever.delete_kb(kb_id)
        self.sparse_retriever.delete_kb(kb_id)

    def _extract_pages(self, extension: str, content: bytes) -> list[tuple[int, str]]:
        if extension == ".pdf":
            reader = PdfReader(BytesIO(content))
            return [
                (page_index + 1, page.extract_text() or "")
                for page_index, page in enumerate(reader.pages)
            ]

        text = content.decode("utf-8", errors="ignore")
        return [(1, text)]
