"""Embedding interface + a deterministic mock implementation.

The real implementation will call OpenAI / a local model. Until then we
use a hashed bag-of-words embedding so cosine similarity between texts
that share vocabulary is meaningful (good enough for tests and the
GET /rag/test endpoint).
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


class Embedder(Protocol):
    @property
    def dimension(self) -> int: ...

    def embed(self, text: str) -> list[float]: ...

    def embed_many(self, texts: list[str]) -> list[list[float]]: ...


class HashedBagOfWordsEmbedder:
    """Deterministic, dependency-free embedder.

    Each token is hashed into one of `dimension` buckets; the vector is
    L2-normalized so cosine similarity works directly. Stopwords are
    removed to reduce noise; light stemming is not applied.
    """

    _STOPWORDS: frozenset[str] = frozenset(
        {
            "a", "an", "the", "and", "or", "but", "if", "of", "in", "on",
            "for", "to", "with", "is", "are", "was", "were", "be", "been",
            "being", "as", "at", "by", "from", "this", "that", "these",
            "those", "it", "its", "we", "our", "you", "your", "they",
            "their", "i", "me", "my", "not", "no", "do", "does", "did",
        }
    )

    def __init__(self, dimension: int = 128) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self._dimension
        for token in self._tokenize(text):
            idx = self._bucket(token)
            vec[idx] += 1.0
        return _l2_normalize(vec)

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]

    def _tokenize(self, text: str) -> list[str]:
        return [
            tok for tok in (m.group(0).lower() for m in _TOKEN_RE.finditer(text))
            if tok not in self._STOPWORDS and len(tok) > 1
        ]

    def _bucket(self, token: str) -> int:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "big") % self._dimension


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]
