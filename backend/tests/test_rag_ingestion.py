from __future__ import annotations

from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from alphalens.rag.embeddings import HashedBagOfWordsEmbedder
from alphalens.rag.ingestion import ingest_directory
from alphalens.rag.retriever import QdrantRetriever


@pytest.fixture
def kb_dir(tmp_path: Path) -> Path:
    (tmp_path / "policy.md").write_text(
        "# Investment Policy\n\n"
        "## Sector limits\n\n"
        "Semiconductors max 35 percent of NAV. Energy max 15 percent.\n\n"
        "## Single name limits\n\n"
        "No single position above 10 percent at cost.\n",
        encoding="utf-8",
    )
    (tmp_path / "risk.md").write_text(
        "# Risk Playbook\n\n"
        "## Drawdown thresholds\n\n"
        "30-day drawdown soft threshold negative 8 percent. Hard threshold negative 12 percent.\n",
        encoding="utf-8",
    )
    return tmp_path


def test_ingest_creates_collection_and_points(kb_dir: Path) -> None:
    client = QdrantClient(location=":memory:")
    embedder = HashedBagOfWordsEmbedder(dimension=64)

    result = ingest_directory(
        kb_dir, client=client, collection="kb_test", embedder=embedder
    )

    assert result.documents == 2
    assert result.chunks >= 3
    assert result.collection == "kb_test"

    info = client.get_collection("kb_test")
    assert info.points_count == result.chunks


def test_ingest_is_idempotent(kb_dir: Path) -> None:
    client = QdrantClient(location=":memory:")
    embedder = HashedBagOfWordsEmbedder(dimension=64)

    first = ingest_directory(kb_dir, client=client, collection="kb_test", embedder=embedder)
    second = ingest_directory(kb_dir, client=client, collection="kb_test", embedder=embedder)

    assert first.chunks == second.chunks
    assert client.get_collection("kb_test").points_count == first.chunks


def test_ingest_missing_directory_raises(tmp_path: Path) -> None:
    client = QdrantClient(location=":memory:")
    embedder = HashedBagOfWordsEmbedder(dimension=32)
    with pytest.raises(FileNotFoundError):
        ingest_directory(
            tmp_path / "nope", client=client, collection="x", embedder=embedder
        )


def test_retriever_returns_chunks_from_ingested_docs(kb_dir: Path) -> None:
    client = QdrantClient(location=":memory:")
    embedder = HashedBagOfWordsEmbedder(dimension=128)
    ingest_directory(kb_dir, client=client, collection="kb_test", embedder=embedder)

    retriever = QdrantRetriever(client=client, collection="kb_test", embedder=embedder)

    chunks = retriever.retrieve("sector limit semiconductors", k=3)
    assert chunks, "expected at least one chunk"
    assert chunks[0].source == "policy.md"
    assert "Sector" in (chunks[0].heading or "") or "sector" in chunks[0].text.lower()
    assert 0.0 <= chunks[0].score <= 1.0


def test_retriever_returns_empty_when_collection_missing() -> None:
    client = QdrantClient(location=":memory:")
    embedder = HashedBagOfWordsEmbedder(dimension=32)
    retriever = QdrantRetriever(client=client, collection="missing", embedder=embedder)
    assert retriever.retrieve("anything", k=3) == []
