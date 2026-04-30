"""RAG service.

Owns the lifecycle of the vector store and retriever and exposes a
small, stable surface to the rest of the app:

- `ensure_indexed()`: lazily ingest the knowledge base on first use.
- `get_relevant_context(query, k=...)`: retrieve top-k chunks for a query.

Designed to be cheap to construct (no I/O at __init__) and idempotent
across calls. Concurrency is not a concern at this scale; if it becomes
one we can guard `_ensure_indexed` with a lock.
"""

from __future__ import annotations

from pathlib import Path

from alphalens.core.config import Settings
from alphalens.core.logging import get_logger
from alphalens.infrastructure.vectorstore import make_qdrant_client
from alphalens.rag.embeddings import Embedder, HashedBagOfWordsEmbedder
from alphalens.rag.ingestion import ingest_directory
from alphalens.rag.retriever import DocumentChunk, QdrantRetriever
from alphalens.services.cache_service import CacheService, build_cache_key

log = get_logger(__name__)

_NAMESPACE = "rag"


class RAGService:
    def __init__(
        self,
        settings: Settings,
        *,
        embedder: Embedder | None = None,
        cache: CacheService | None = None,
    ) -> None:
        self._settings = settings
        self._embedder = embedder or HashedBagOfWordsEmbedder(
            dimension=settings.rag_embedding_dim
        )
        self._client = make_qdrant_client(settings)
        self._retriever = QdrantRetriever(
            client=self._client,
            collection=settings.rag_collection,
            embedder=self._embedder,
        )
        self._indexed = False
        self._cache = cache

    def ensure_indexed(self) -> None:
        """Ingest the knowledge base if it has not been ingested yet."""

        if self._indexed:
            return
        kb_path = _resolve_kb_path(self._settings.knowledge_base_path)
        if not kb_path.exists():
            log.warning("rag_kb_missing", path=str(kb_path))
            self._indexed = True
            return

        result = ingest_directory(
            kb_path,
            client=self._client,
            collection=self._settings.rag_collection,
            embedder=self._embedder,
        )
        log.info(
            "rag_indexed",
            documents=result.documents,
            chunks=result.chunks,
            collection=result.collection,
        )
        self._indexed = True

    def get_relevant_context(self, query: str, *, k: int = 5) -> list[DocumentChunk]:
        """Return the top-k chunks most relevant to `query`."""

        self.ensure_indexed()

        cached = self._get_cached_chunks(query, k)
        if cached is not None:
            return cached

        chunks = self._retriever.retrieve(query, k=k)
        self._set_cached_chunks(query, k, chunks)
        return chunks

    # ------------------------------------------------------------------
    # Internal cache helpers
    # ------------------------------------------------------------------

    def _cache_key(self, query: str, k: int) -> str:
        return build_cache_key(
            _NAMESPACE,
            {
                "q": query.strip().lower(),
                "k": k,
                "collection": self._settings.rag_collection,
            },
        )

    def _get_cached_chunks(self, query: str, k: int) -> list[DocumentChunk] | None:
        if self._cache is None:
            return None
        raw = self._cache.get_cached(self._cache_key(query, k))
        if not isinstance(raw, list):
            return None
        try:
            return [
                DocumentChunk(
                    source=item["source"],
                    heading=item.get("heading"),
                    text=item["text"],
                    score=float(item["score"]),
                    chunk_id=item["chunk_id"],
                )
                for item in raw
            ]
        except (KeyError, TypeError, ValueError) as exc:
            log.warning("rag cache decode failed: %s", exc)
            self._cache.delete(self._cache_key(query, k))
            return None

    def _set_cached_chunks(
        self, query: str, k: int, chunks: list[DocumentChunk]
    ) -> None:
        if self._cache is None:
            return
        payload = [
            {
                "source": c.source,
                "heading": c.heading,
                "text": c.text,
                "score": c.score,
                "chunk_id": c.chunk_id,
            }
            for c in chunks
        ]
        self._cache.set_cached(self._cache_key(query, k), payload)


def _resolve_kb_path(configured: str) -> Path:
    """Resolve the knowledge-base directory.

    Absolute paths are used as-is. Relative paths are tried against the
    current working directory first, then against parents of this file
    (so the service works whether launched from `backend/` or repo root).
    """

    p = Path(configured)
    if p.is_absolute():
        return p

    cwd_candidate = Path.cwd() / p
    if cwd_candidate.exists():
        return cwd_candidate

    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / p
        if candidate.exists():
            return candidate
    return cwd_candidate
