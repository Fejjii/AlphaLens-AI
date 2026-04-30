"""Qdrant client factory.

Returns an in-memory client when no `QDRANT_URL` is configured. This
keeps tests hermetic and the dev experience zero-config; production
overrides the URL via env.
"""

from __future__ import annotations

from qdrant_client import QdrantClient

from alphalens.core.config import Settings


def get_qdrant_url(settings: Settings) -> str | None:
    return settings.qdrant_url


def make_qdrant_client(settings: Settings) -> QdrantClient:
    if settings.qdrant_url:
        return QdrantClient(url=settings.qdrant_url)
    return QdrantClient(location=":memory:")
