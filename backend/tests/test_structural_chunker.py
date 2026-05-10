from chunking.structural_chunker import StructuralChunker


def test_structural_chunker_keeps_section_metadata() -> None:
    chunker = StructuralChunker(max_tokens=40, overlap_tokens=10)
    pages = [
        (
            1,
            "# Overview\n\nThis is the first paragraph.\n\n"
            "## Details\n\nThis section contains more detailed technical content.",
        )
    ]

    chunks = chunker.chunk_document(
        kb_id="architecture",
        kb_name="Architecture",
        document_id="architecture-sample-123",
        filename="sample.md",
        source="sample.md",
        pages=pages,
    )

    assert len(chunks) >= 2
    assert chunks[0].section == "Overview"
    assert all(chunk.kb_id == "architecture" for chunk in chunks)
    assert all(chunk.kb_name == "Architecture" for chunk in chunks)
    assert all(chunk.document_id == "architecture-sample-123" for chunk in chunks)
    assert any(chunk.section == "Details" for chunk in chunks)
    assert all(chunk.token_count > 0 for chunk in chunks)
