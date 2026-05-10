from __future__ import annotations

import re
from collections.abc import Iterable

import tiktoken

from models import ChunkMetadata
from rag.metadata import build_chunk_id

HEADING_PATTERN = re.compile(r"^(#{1,6}\s+.+|\d+(?:\.\d+)*\s+.+|[A-Z][A-Z0-9\s\-:/]{3,})$")
TOKEN_FALLBACK_PATTERN = re.compile(r"\S+")


class StructuralChunker:
    def __init__(self, max_tokens: int = 450, overlap_tokens: int = 80) -> None:
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self._encoding = tiktoken.get_encoding("cl100k_base")

    def chunk_document(
        self,
        kb_id: str,
        kb_name: str,
        document_id: str,
        filename: str,
        source: str,
        pages: Iterable[tuple[int, str]],
    ) -> list[ChunkMetadata]:
        chunks: list[ChunkMetadata] = []
        ordinal = 0

        for page_number, raw_text in pages:
            text = raw_text.strip()
            if not text:
                continue

            current_section = "Overview"
            section_buffer: list[str] = []
            for block in self._split_blocks(text):
                if self._looks_like_heading(block):
                    ordinal = self._flush_section(
                        kb_id=kb_id,
                        kb_name=kb_name,
                        document_id=document_id,
                        filename=filename,
                        source=source,
                        page=page_number,
                        section=current_section,
                        section_text="\n\n".join(section_buffer),
                        ordinal=ordinal,
                        output=chunks,
                    )
                    current_section = self._clean_heading(block)
                    section_buffer = []
                    continue
                section_buffer.append(block)

            ordinal = self._flush_section(
                kb_id=kb_id,
                kb_name=kb_name,
                document_id=document_id,
                filename=filename,
                source=source,
                page=page_number,
                section=current_section,
                section_text="\n\n".join(section_buffer),
                ordinal=ordinal,
                output=chunks,
            )

        return chunks

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        try:
            return len(self._encoding.encode(text))
        except Exception:
            return len(TOKEN_FALLBACK_PATTERN.findall(text))

    def _flush_section(
        self,
        kb_id: str,
        kb_name: str,
        document_id: str,
        filename: str,
        source: str,
        page: int,
        section: str,
        section_text: str,
        ordinal: int,
        output: list[ChunkMetadata],
    ) -> int:
        normalized = section_text.strip()
        if not normalized:
            return ordinal

        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()]
        buffer: list[str] = []

        for paragraph in paragraphs:
            candidate = "\n\n".join([*buffer, paragraph])
            if buffer and self.count_tokens(candidate) > self.max_tokens:
                ordinal = self._append_chunk(
                    kb_id=kb_id,
                    kb_name=kb_name,
                    document_id=document_id,
                    filename=filename,
                    source=source,
                    page=page,
                    section=section,
                    text="\n\n".join(buffer),
                    ordinal=ordinal,
                    output=output,
                )
                overlap_text = self._make_overlap("\n\n".join(buffer))
                buffer = [part for part in [overlap_text, paragraph] if part]
                continue
            buffer.append(paragraph)

        if buffer:
            ordinal = self._append_chunk(
                kb_id=kb_id,
                kb_name=kb_name,
                document_id=document_id,
                filename=filename,
                source=source,
                page=page,
                section=section,
                text="\n\n".join(buffer),
                ordinal=ordinal,
                output=output,
            )

        return ordinal

    def _append_chunk(
        self,
        kb_id: str,
        kb_name: str,
        document_id: str,
        filename: str,
        source: str,
        page: int,
        section: str,
        text: str,
        ordinal: int,
        output: list[ChunkMetadata],
    ) -> int:
        clean_text = text.strip()
        if not clean_text:
            return ordinal

        chunk = ChunkMetadata(
            chunk_id=build_chunk_id(
                kb_id=kb_id,
                document_id=document_id,
                filename=filename,
                page=page,
                section=section,
                ordinal=ordinal,
                text=clean_text,
            ),
            kb_id=kb_id,
            kb_name=kb_name,
            document_id=document_id,
            source=source,
            filename=filename,
            page=page,
            section=section,
            text=clean_text,
            token_count=self.count_tokens(clean_text),
        )
        output.append(chunk)
        return ordinal + 1

    def _make_overlap(self, text: str) -> str:
        if self.overlap_tokens <= 0:
            return ""
        words = text.split()
        if not words:
            return ""

        overlap_words = min(len(words), max(20, self.overlap_tokens // 2))
        return " ".join(words[-overlap_words:])

    def _split_blocks(self, text: str) -> list[str]:
        lines = [line.rstrip() for line in text.splitlines()]
        blocks: list[str] = []
        buffer: list[str] = []

        for line in lines:
            if not line.strip():
                if buffer:
                    blocks.append("\n".join(buffer).strip())
                    buffer = []
                continue
            buffer.append(line)

        if buffer:
            blocks.append("\n".join(buffer).strip())

        return blocks

    def _looks_like_heading(self, block: str) -> bool:
        single_line = " ".join(part.strip() for part in block.splitlines()).strip()
        if "\n" in block:
            return False
        return bool(HEADING_PATTERN.match(single_line)) and len(single_line.split()) <= 16

    def _clean_heading(self, block: str) -> str:
        heading = block.lstrip("#").strip()
        return heading.rstrip(":") or "Overview"
