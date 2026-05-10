from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader

from chunking.structural_chunker import StructuralChunker
from config import Settings
from models import UploadResponse
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
    ) -> None:
        self.settings = settings
        self.chunker = chunker
        self.dense_retriever = dense_retriever
        self.sparse_retriever = sparse_retriever

    async def ingest_upload(self, upload: UploadFile) -> UploadResponse:
        filename = Path(upload.filename or "document").name
        extension = Path(filename).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {extension}")

        content = await upload.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty upload")

        stored_path = self._store_upload(filename, content)
        pages = self._extract_pages(extension, content)
        chunks = self.chunker.chunk_document(
            filename=filename,
            source=stored_path.as_posix(),
            pages=pages,
        )

        self.dense_retriever.upsert(chunks)
        self.sparse_retriever.upsert(chunks)

        return UploadResponse(filename=filename, ingested_chunks=len(chunks))

    def indexed_chunks(self) -> int:
        return self.sparse_retriever.total_chunks()

    def _store_upload(self, filename: str, content: bytes) -> Path:
        stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        target = self.settings.uploads_dir / f"{stamp}-{filename}"
        target.write_bytes(content)
        return target

    def _extract_pages(self, extension: str, content: bytes) -> list[tuple[int, str]]:
        if extension == ".pdf":
            reader = PdfReader(BytesIO(content))
            return [
                (page_index + 1, page.extract_text() or "")
                for page_index, page in enumerate(reader.pages)
            ]

        text = content.decode("utf-8", errors="ignore")
        return [(1, text)]
