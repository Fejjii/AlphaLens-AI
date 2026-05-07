"""RAG service.

Owns indexing, retrieval, and knowledge-base inspection APIs used by:
- agent runtime retrieval (`get_relevant_context`)
- knowledge management endpoints (list, stats, upload, search)

The service prefers vector retrieval via Qdrant and deterministically
falls back to lexical retrieval when vector infrastructure is unavailable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphalens.core.config import Settings
from alphalens.core.logging import get_logger
from alphalens.infrastructure.vectorstore import make_qdrant_client
from alphalens.rag.chunking import chunk_markdown
from alphalens.rag.embeddings import Embedder, HashedBagOfWordsEmbedder
from alphalens.rag.ingestion import ingest_directory
from alphalens.rag.retriever import DocumentChunk, QdrantRetriever
from alphalens.services.cache_service import CacheService, build_cache_key
from alphalens.schemas.knowledge import (
    KnowledgeDocument,
    KnowledgeSearchResponse,
    KnowledgeSearchResult,
    KnowledgeStatsResponse,
)

log = get_logger(__name__)

_NAMESPACE = "rag"
_UPLOAD_DIR = "uploads"
_SUPPORTED_SUFFIXES = (".md", ".txt")
_DEFAULT_MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class _IndexedDocument:
    document_id: str
    title: str
    source: str
    file_type: str
    chunk_count: int
    indexed_at: datetime
    collection: str
    seeded: bool = False


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
        self._documents: dict[str, _IndexedDocument] = {}
        self._chunk_store: list[tuple[_IndexedDocument, DocumentChunk]] = []

    def ensure_indexed(self) -> None:
        """Ingest the knowledge base if it has not been ingested yet."""

        if self._indexed:
            return
        kb_path = _resolve_kb_path(self._settings.knowledge_base_path)
        if not kb_path.exists():
            log.warning("rag_kb_missing", path=str(kb_path))
            self._indexed = True
            return

        try:
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
        except Exception as exc:  # noqa: BLE001 - vector store can be unavailable.
            log.warning("rag_indexing_fallback", error=str(exc))

        self._refresh_indexed_documents(kb_path)
        self._indexed = True

    def get_relevant_context(self, query: str, *, k: int = 5) -> list[DocumentChunk]:
        """Return the top-k chunks most relevant to `query`."""

        self.ensure_indexed()

        cached = self._get_cached_chunks(query, k)
        if cached is not None:
            return cached

        chunks: list[DocumentChunk]
        try:
            chunks = self._retriever.retrieve(query, k=k)
        except Exception as exc:  # noqa: BLE001 - remote Qdrant may be down.
            log.warning("rag_vector_retrieval_fallback", error=str(exc))
            chunks = []
        if not chunks:
            chunks = self._fallback_retrieve(query, k=k)
        self._set_cached_chunks(query, k, chunks)
        return chunks

    @property
    def vector_mode(self) -> str:
        if self._settings.qdrant_url:
            return "qdrant"
        return "deterministic_fallback"

    @property
    def max_upload_bytes(self) -> int:
        return _DEFAULT_MAX_UPLOAD_BYTES

    @property
    def supported_file_types(self) -> list[str]:
        return list(_SUPPORTED_SUFFIXES)

    def list_documents(self) -> list[KnowledgeDocument]:
        self.ensure_indexed()
        docs = sorted(
            self._documents.values(),
            key=lambda item: item.indexed_at,
            reverse=True,
        )
        return [self._to_knowledge_document(doc) for doc in docs]

    def get_stats(self) -> KnowledgeStatsResponse:
        self.ensure_indexed()
        docs = list(self._documents.values())
        seeded = sum(1 for doc in docs if doc.seeded)
        uploaded = len(docs) - seeded
        seeded_titles = sorted(doc.title for doc in docs if doc.seeded)
        uploaded_titles = sorted(doc.title for doc in docs if not doc.seeded)
        return KnowledgeStatsResponse(
            document_count=len(docs),
            chunk_count=sum(doc.chunk_count for doc in docs),
            collection=self._settings.rag_collection,
            vector_mode=self.vector_mode,
            seeded_documents=seeded,
            uploaded_documents=uploaded,
            seeded_source_titles=seeded_titles,
            uploaded_source_titles=uploaded_titles,
        )

    def search(self, query: str, *, k: int = 5) -> KnowledgeSearchResponse:
        chunks = self.get_relevant_context(query, k=k)
        results: list[KnowledgeSearchResult] = []
        for chunk in chunks:
            doc = self._documents.get(chunk.source)
            if doc is None:
                doc = _IndexedDocument(
                    document_id=f"doc_{_safe_slug(chunk.source)}",
                    title=_title_from_source(chunk.source),
                    source=chunk.source,
                    file_type=Path(chunk.source).suffix.lstrip(".") or "txt",
                    chunk_count=0,
                    indexed_at=datetime.now(tz=UTC),
                    collection=self._settings.rag_collection,
                )
            results.append(
                KnowledgeSearchResult(
                    document_id=doc.document_id,
                    document_title=doc.title,
                    chunk_id=chunk.chunk_id,
                    source=chunk.source,
                    score=chunk.score,
                    snippet=chunk.text[:320],
                    section=chunk.heading,
                )
            )
        retrieval_mode = "vector" if self.vector_mode == "qdrant" else "deterministic_fallback"
        return KnowledgeSearchResponse(
            query=query,
            k=k,
            results=results,
            retrieval_mode=retrieval_mode,
        )

    def upload_document(self, *, filename: str, content: bytes) -> KnowledgeDocument:
        suffix = Path(filename).suffix.lower()
        if suffix not in _SUPPORTED_SUFFIXES:
            raise ValueError(
                f"Unsupported file type '{suffix or 'unknown'}'. "
                f"Supported types: {', '.join(_SUPPORTED_SUFFIXES)}"
            )
        if len(content) > self.max_upload_bytes:
            raise ValueError(
                f"File exceeds maximum size of {self.max_upload_bytes} bytes."
            )
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Only UTF-8 text files are supported right now.") from exc

        kb_path = _resolve_kb_path(self._settings.knowledge_base_path)
        upload_dir = kb_path / _UPLOAD_DIR
        upload_dir.mkdir(parents=True, exist_ok=True)

        stem = _safe_slug(Path(filename).stem)
        now = datetime.now(tz=UTC)
        target = upload_dir / f"{stem}_{now.strftime('%Y%m%d%H%M%S')}{suffix}"
        target.write_text(text, encoding="utf-8")

        self._indexed = False
        self.ensure_indexed()

        relative_source = target.relative_to(kb_path).as_posix()
        doc = self._documents.get(relative_source)
        if doc is None:
            doc = _IndexedDocument(
                document_id=f"doc_{_safe_slug(relative_source)}",
                title=Path(filename).stem.strip() or "Uploaded document",
                source=relative_source,
                file_type=suffix.lstrip("."),
                chunk_count=max(len(chunk_markdown(text)), 1),
                indexed_at=now,
                collection=self._settings.rag_collection,
                seeded=False,
            )
            self._documents[relative_source] = doc
        return self._to_knowledge_document(doc)

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

    def _refresh_indexed_documents(self, kb_root: Path) -> None:
        self._documents = {}
        self._chunk_store = []
        now = datetime.now(tz=UTC)
        for path in _iter_supported_files(kb_root):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if not text.strip():
                continue
            rel = path.relative_to(kb_root).as_posix()
            chunks = chunk_markdown(text)
            doc = _IndexedDocument(
                document_id=f"doc_{_safe_slug(rel)}",
                title=_title_from_source(rel),
                source=rel,
                file_type=path.suffix.lstrip("."),
                chunk_count=len(chunks),
                indexed_at=datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
                if path.exists()
                else now,
                collection=self._settings.rag_collection,
                seeded=not rel.startswith(f"{_UPLOAD_DIR}/"),
            )
            self._documents[rel] = doc
            for chunk in chunks:
                self._chunk_store.append(
                    (
                        doc,
                        DocumentChunk(
                            source=rel,
                            heading=chunk.heading,
                            text=chunk.text,
                            score=0.0,
                            chunk_id=f"{doc.document_id}:{chunk.order}",
                        ),
                    )
                )

    def _fallback_retrieve(self, query: str, *, k: int) -> list[DocumentChunk]:
        tokens = _tokenize(query)
        if not tokens:
            return []
        scored: list[DocumentChunk] = []
        for _doc, chunk in self._chunk_store:
            hay = _tokenize(f"{chunk.heading or ''} {chunk.text}")
            overlap = len(tokens & hay)
            if overlap <= 0:
                continue
            score = min(1.0, overlap / max(len(tokens), 1))
            scored.append(
                DocumentChunk(
                    source=chunk.source,
                    heading=chunk.heading,
                    text=chunk.text,
                    score=score,
                    chunk_id=chunk.chunk_id,
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:k]

    def _to_knowledge_document(self, doc: _IndexedDocument) -> KnowledgeDocument:
        return KnowledgeDocument(
            document_id=doc.document_id,
            document_title=doc.title,
            source=doc.source,
            file_type=doc.file_type,
            chunk_count=doc.chunk_count,
            indexed_at=doc.indexed_at,
            collection=doc.collection,
            status="indexed",
        )


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


def _iter_supported_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for suffix in _SUPPORTED_SUFFIXES:
        files.extend(root.rglob(f"*{suffix}"))
    return sorted(files)


def _safe_slug(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip())
    return clean.strip("-").lower() or "document"


def _title_from_source(source: str) -> str:
    return Path(source).stem.replace("_", " ").replace("-", " ").strip().title()


def _tokenize(text: str) -> set[str]:
    return {tok for tok in re.findall(r"[a-zA-Z0-9]{2,}", text.lower())}
