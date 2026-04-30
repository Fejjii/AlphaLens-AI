from __future__ import annotations

from alphalens.rag.chunking import chunk_markdown


def test_chunks_split_on_headings() -> None:
    md = (
        "# Title\n\nIntro paragraph.\n\n"
        "## Section A\n\nAlpha content.\n\n"
        "## Section B\n\nBeta content.\n"
    )
    chunks = chunk_markdown(md)
    assert len(chunks) == 3
    headings = [c.heading for c in chunks]
    assert headings == ["Title", "Section A", "Section B"]
    assert chunks[1].text.startswith("Alpha")


def test_long_section_is_split() -> None:
    paragraphs = "\n\n".join(["lorem ipsum " * 40 for _ in range(5)])
    md = f"## Big section\n\n{paragraphs}\n"
    chunks = chunk_markdown(md, max_chars=500)
    assert len(chunks) > 1
    assert all(c.heading == "Big section" for c in chunks)


def test_empty_document_yields_no_chunks() -> None:
    assert chunk_markdown("") == []
    assert chunk_markdown("\n\n   \n") == []
