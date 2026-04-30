"""Retriever interfaces + a Qdrant-backed implementation.

The agent only ever sees the `Retriever` Protocol. Concrete backends
(Qdrant today; pgvector / hybrid search later) plug in behind it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Protocol, Sequence

from qdrant_client import QdrantClient

from alphalens.rag.embeddings import Embedder


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    """A retrieved chunk with its provenance and score."""

    source: str
    heading: str | None
    text: str
    score: float
    chunk_id: str


class Retriever(Protocol):
    def retrieve(self, query: str, *, k: int = 5) -> list[DocumentChunk]: ...


class NoopRetriever:
    """Safe default; returns no documents."""

    def retrieve(self, query: str, *, k: int = 5) -> list[DocumentChunk]:
        del query, k
        return []


class QdrantRetriever:
    """Vector retriever backed by Qdrant."""

    def __init__(
        self,
        *,
        client: QdrantClient,
        collection: str,
        embedder: Embedder,
    ) -> None:
        self._client = client
        self._collection = collection
        self._embedder = embedder

    def retrieve(self, query: str, *, k: int = 5) -> list[DocumentChunk]:
        if k <= 0:
            return []
        if not self._collection_exists():
            return []

        vector = self._embedder.embed(query)
        results = self._search_points(vector, k)
        return [_to_chunk(r) for r in results]

    def _search_points(self, vector: Sequence[float], k: int) -> Iterable[Any]:
        """Run a similarity search against Qdrant using whichever API exists.

        Older qdrant-client exposes ``search``; newer versions use ``query_points``
        and return an object with a ``.points`` attribute. We normalize both
        into an iterable of scored points.
        """
        search = getattr(self._client, "search", None)
        if callable(search):
            return search(
                collection_name=self._collection,
                query_vector=vector,
                limit=k,
                with_payload=True,
            )

        response = self._client.query_points(
            collection_name=self._collection,
            query=vector,
            limit=k,
            with_payload=True,
        )
        points = getattr(response, "points", None)
        if points is not None:
            return points
        return response  # assume already iterable

    def _collection_exists(self) -> bool:
        try:
            self._client.get_collection(self._collection)
            return True
        except Exception:  # noqa: BLE001 - qdrant raises a generic ApiException
            return False


def _to_chunk(point: Any) -> DocumentChunk:
    payload = getattr(point, "payload", None) or {}
    score = getattr(point, "score", 0.0) or 0.0
    point_id = getattr(point, "id", "")
    return DocumentChunk(
        source=str(payload.get("source", "")),
        heading=payload.get("heading"),
        text=str(payload.get("text", "")),
        score=float(score),
        chunk_id=str(point_id),
    )
