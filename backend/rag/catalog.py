from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from fastapi import HTTPException

from config import Settings
from models import DocumentRecord, KnowledgeBaseRecord


class MetadataCatalog:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._ensure_store_files()

    def list_kbs(self) -> list[KnowledgeBaseRecord]:
        kb_map = self._load_kb_map()
        documents = self._load_documents()
        counts: dict[str, tuple[int, int]] = {}

        for document in documents:
            doc_count, chunk_count = counts.get(document.kb_id, (0, 0))
            counts[document.kb_id] = (doc_count + 1, chunk_count + document.chunk_count)

        return [
            KnowledgeBaseRecord(
                id=kb_id,
                name=name,
                documents=counts.get(kb_id, (0, 0))[0],
                chunks=counts.get(kb_id, (0, 0))[1],
            )
            for kb_id, name in sorted(kb_map.items())
        ]

    def create_kb(self, kb_id: str, name: str) -> KnowledgeBaseRecord:
        kb_map = self._load_kb_map()
        if kb_id in kb_map:
            raise HTTPException(status_code=409, detail=f"Knowledge base already exists: {kb_id}")
        kb_map[kb_id] = name
        self._save_kb_map(kb_map)
        return KnowledgeBaseRecord(id=kb_id, name=name, documents=0, chunks=0)

    def upsert_kb(self, kb_id: str, name: str) -> KnowledgeBaseRecord:
        kb_map = self._load_kb_map()
        kb_map[kb_id] = name
        self._save_kb_map(kb_map)

        for kb in self.list_kbs():
            if kb.id == kb_id:
                return kb

        return KnowledgeBaseRecord(id=kb_id, name=name, documents=0, chunks=0)

    def rename_kb(self, kb_id: str, name: str) -> KnowledgeBaseRecord:
        kb_map = self._load_kb_map()
        if kb_id not in kb_map:
            raise HTTPException(status_code=404, detail=f"Unknown knowledge base: {kb_id}")

        kb_map[kb_id] = name
        self._save_kb_map(kb_map)

        documents = self._load_documents()
        updated_documents = [
            document.model_copy(update={"kb_name": name}) if document.kb_id == kb_id else document
            for document in documents
        ]
        self._save_documents(updated_documents)

        for kb in self.list_kbs():
            if kb.id == kb_id:
                return kb

        raise HTTPException(status_code=404, detail=f"Unknown knowledge base: {kb_id}")

    def delete_kb(self, kb_id: str) -> bool:
        kb_map = self._load_kb_map()
        deleted = kb_id in kb_map

        if deleted:
            kb_map.pop(kb_id)
            self._save_kb_map(kb_map)

        documents = [document for document in self._load_documents() if document.kb_id != kb_id]
        self._save_documents(documents)
        return deleted

    def get_kb(self, kb_id: str) -> KnowledgeBaseRecord:
        for kb in self.list_kbs():
            if kb.id == kb_id:
                return kb
        raise HTTPException(status_code=404, detail=f"Unknown knowledge base: {kb_id}")

    def list_documents(self, kb_id: str) -> list[DocumentRecord]:
        self.get_kb(kb_id)
        return [document for document in self._load_documents() if document.kb_id == kb_id]

    def upsert_document(self, document: DocumentRecord) -> DocumentRecord:
        self.get_kb(document.kb_id)
        documents = [
            item for item in self._load_documents() if item.document_id != document.document_id
        ]
        documents.append(document)
        self._save_documents(documents)
        return document

    def replace_documents(self, kb_id: str, documents: Iterable[DocumentRecord]) -> list[DocumentRecord]:
        replacement = list(documents)
        current_documents = [item for item in self._load_documents() if item.kb_id != kb_id]
        current_documents.extend(replacement)
        self._save_documents(current_documents)
        return replacement

    def delete_document(self, kb_id: str, document_id: str) -> DocumentRecord:
        self.get_kb(kb_id)
        documents = self._load_documents()
        target = next(
            (
                document
                for document in documents
                if document.kb_id == kb_id and document.document_id == document_id
            ),
            None,
        )
        if target is None:
            raise HTTPException(status_code=404, detail=f"Unknown document: {document_id}")

        self._save_documents(
            [
                document
                for document in documents
                if not (document.kb_id == kb_id and document.document_id == document_id)
            ],
        )
        return target

    def _ensure_store_files(self) -> None:
        self.settings.knowledge_bases_store_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.settings.knowledge_bases_store_path.exists():
            self.settings.knowledge_bases_store_path.write_text("{}", encoding="utf-8")
        if not self.settings.documents_store_path.exists():
            self.settings.documents_store_path.write_text("[]", encoding="utf-8")

    def _load_kb_map(self) -> dict[str, str]:
        return json.loads(self.settings.knowledge_bases_store_path.read_text(encoding="utf-8"))

    def _save_kb_map(self, kb_map: dict[str, str]) -> None:
        self.settings.knowledge_bases_store_path.write_text(
            json.dumps(kb_map, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_documents(self) -> list[DocumentRecord]:
        raw_documents = json.loads(self.settings.documents_store_path.read_text(encoding="utf-8"))
        return [DocumentRecord.model_validate(item) for item in raw_documents]

    def _save_documents(self, documents: Iterable[DocumentRecord]) -> None:
        payload = [document.model_dump(mode="json") for document in documents]
        self.settings.documents_store_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )