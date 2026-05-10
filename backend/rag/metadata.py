from __future__ import annotations

import hashlib
from uuid import NAMESPACE_URL, uuid5
from pathlib import Path


def build_document_id(kb_id: str, filename: str, content: bytes) -> str:
    digest = hashlib.sha1(content).hexdigest()[:12]
    safe_name = Path(filename).stem.replace(" ", "-").lower()
    return f"{kb_id}-{safe_name}-{digest}"


def build_chunk_id(
    kb_id: str,
    document_id: str,
    filename: str,
    page: int | None,
    section: str | None,
    ordinal: int,
    text: str,
) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    safe_name = Path(filename).stem.replace(" ", "-").lower()
    page_part = str(page or 0)
    section_part = (section or "section").strip().replace(" ", "-").lower()
    return f"{kb_id}-{document_id}-{safe_name}-{page_part}-{section_part}-{ordinal}-{digest}"


def build_qdrant_point_id(chunk_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, chunk_id))
