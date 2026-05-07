"""RAG ingestion pipeline.

Reads markdown and plain-text files from disk, chunks them, embeds them,
and upserts the resulting points into a Qdrant collection. Idempotent:
re-running ingestion replaces existing points for the same `(source, order)`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from alphalens.core.logging import get_logger
from alphalens.rag.chunking import Chunk, chunk_markdown
from alphalens.rag.embeddings import Embedder

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class IngestionResult:
    documents: int
    chunks: int
    collection: str


def ensure_collection(client: QdrantClient, collection: str, dimension: int) -> None:
    """Create the collection if it does not already exist."""

    existing = {c.name for c in client.get_collections().collections}
    if collection in existing:
        return
    client.create_collection(
        collection_name=collection,
        vectors_config=qmodels.VectorParams(
            size=dimension,
            distance=qmodels.Distance.COSINE,
        ),
    )
    log.info("rag_collection_created", collection=collection, dim=dimension)


def ingest_directory(
    directory: Path,
    *,
    client: QdrantClient,
    collection: str,
    embedder: Embedder,
) -> IngestionResult:
    """Ingest every supported knowledge file under `directory` into Qdrant.

    Args:
        directory: Root path to scan recursively for markdown files.
        client: Qdrant client (in-memory acceptable).
        collection: Target collection name; created if missing.
        embedder: Concrete embedder.

    Returns:
        Counts for observability.
    """

    if not directory.exists():
        raise FileNotFoundError(f"Knowledge base directory not found: {directory}")

    ensure_collection(client, collection, embedder.dimension)

    files = sorted([*directory.rglob("*.md"), *directory.rglob("*.txt")])
    points: list[qmodels.PointStruct] = []
    doc_count = 0

    for path in files:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            continue
        doc_count += 1
        source = path.relative_to(directory).as_posix()
        chunks = chunk_markdown(text)
        if not chunks:
            continue

        vectors = embedder.embed_many([c.text for c in chunks])
        for chunk, vector in zip(chunks, vectors, strict=True):
            points.append(_to_point(source=source, chunk=chunk, vector=vector))

    if points:
        client.upsert(collection_name=collection, points=points, wait=True)

    log.info(
        "rag_ingest_complete",
        directory=str(directory),
        documents=doc_count,
        chunks=len(points),
        collection=collection,
    )
    return IngestionResult(
        documents=doc_count, chunks=len(points), collection=collection
    )


def _to_point(*, source: str, chunk: Chunk, vector: list[float]) -> qmodels.PointStruct:
    point_id = _stable_id(source=source, order=chunk.order)
    return qmodels.PointStruct(
        id=point_id,
        vector=vector,
        payload={
            "source": source,
            "heading": chunk.heading,
            "text": chunk.text,
            "order": chunk.order,
        },
    )


def _stable_id(*, source: str, order: int) -> int:
    """Deterministic 63-bit integer id derived from (source, order).

    Qdrant accepts unsigned 64-bit ints; we keep the high bit clear so
    Python's signed int round-trip is unambiguous.
    """

    digest = hashlib.blake2b(
        f"{source}#{order}".encode("utf-8"), digest_size=8
    ).digest()
    return int.from_bytes(digest, "big") & 0x7FFFFFFFFFFFFFFF
