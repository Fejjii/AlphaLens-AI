"""Cache backends.

Two implementations behind a single ``CacheBackend`` protocol:

- ``InMemoryCacheBackend``: process-local dict with per-key TTL. Used as the
  default and as a graceful fallback whenever Redis is unreachable.
- ``RedisCacheBackend``: thin wrapper over the synchronous ``redis`` client.
  Every operation is wrapped in a try/except so any I/O failure logs a warning
  and degrades to a no-op rather than propagating to the caller.

JSON serialisation lives in this module (``set_json`` / ``get_json``) so the
service layer can stay agnostic of the underlying storage format.
"""

from __future__ import annotations

import json
import time
from threading import Lock
from typing import Any, Protocol

from alphalens.core.config import Settings
from alphalens.core.logging import get_logger

logger = get_logger(__name__)

# JSON-serialisable values that the cache contract supports.
JSONValue = dict[str, Any] | list[Any] | str | int | float | bool | None


class CacheBackend(Protocol):
    """Minimal cache contract used by the service layer."""

    def get_json(self, key: str) -> JSONValue: ...

    def set_json(
        self, key: str, value: JSONValue, ttl_seconds: int | None = None
    ) -> None: ...

    def delete(self, key: str) -> None: ...


# ---------------------------------------------------------------------------
# In-memory backend
# ---------------------------------------------------------------------------


class InMemoryCacheBackend:
    """Thread-safe in-process cache with per-key absolute expiry timestamps.

    Suitable for single-process deployments and as a transparent fallback when
    Redis is misconfigured or unreachable. Not LRU: this is intentionally
    minimal — total entries are expected to be small at this scale.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[JSONValue, float | None]] = {}
        self._lock = Lock()

    def get_json(self, key: str) -> JSONValue:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if expires_at is not None and time.monotonic() >= expires_at:
                self._store.pop(key, None)
                return None
            return value

    def set_json(
        self, key: str, value: JSONValue, ttl_seconds: int | None = None
    ) -> None:
        expires_at = time.monotonic() + ttl_seconds if ttl_seconds else None
        with self._lock:
            self._store[key] = (value, expires_at)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        """Test-only helper; not part of the protocol."""
        with self._lock:
            self._store.clear()


# ---------------------------------------------------------------------------
# Redis backend
# ---------------------------------------------------------------------------


class RedisCacheBackend:
    """Redis-backed cache. Failures degrade to no-ops with a warning log."""

    def __init__(self, *, redis_url: str, client: Any | None = None) -> None:
        self._url = redis_url
        if client is not None:
            self._client = client
            return
        try:
            import redis  # local import keeps redis-py optional

            self._client = redis.Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
        except Exception as exc:
            logger.warning("redis_cache_init_failed", error=str(exc))
            self._client = None

    def get_json(self, key: str) -> JSONValue:
        if self._client is None:
            return None
        try:
            raw = self._client.get(key)
        except Exception as exc:
            logger.warning("redis_cache_get_failed", key=key, error=str(exc))
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError) as exc:
            logger.warning("redis_cache_decode_failed", key=key, error=str(exc))
            return None

    def set_json(
        self, key: str, value: JSONValue, ttl_seconds: int | None = None
    ) -> None:
        if self._client is None:
            return
        try:
            payload = json.dumps(value, default=str)
        except (TypeError, ValueError) as exc:
            logger.warning("redis_cache_encode_failed", key=key, error=str(exc))
            return
        try:
            if ttl_seconds and ttl_seconds > 0:
                self._client.set(key, payload, ex=ttl_seconds)
            else:
                self._client.set(key, payload)
        except Exception as exc:
            logger.warning("redis_cache_set_failed", key=key, error=str(exc))

    def delete(self, key: str) -> None:
        if self._client is None:
            return
        try:
            self._client.delete(key)
        except Exception as exc:
            logger.warning("redis_cache_delete_failed", key=key, error=str(exc))


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_cache_backend(settings: Settings) -> CacheBackend:
    """Build the cache backend for *settings*.

    Selection rule:
        if cache_enabled and redis_url: try Redis (falls back to memory on
        connection failure). Otherwise: in-memory.
    """
    if not settings.cache_enabled:
        return InMemoryCacheBackend()
    if not settings.redis_url:
        return InMemoryCacheBackend()

    backend = RedisCacheBackend(redis_url=settings.redis_url)
    # Probe the connection eagerly so wiring is visible at startup. Any failure
    # is silently swapped for the in-memory backend so the app boots regardless.
    try:
        if backend._client is None:
            raise RuntimeError("redis client is None")
        backend._client.ping()
        logger.info("cache_backend_redis", url=settings.redis_url)
        return backend
    except Exception as exc:
        logger.warning(
            "cache_backend_redis_unavailable",
            url=settings.redis_url,
            error=str(exc),
        )
        return InMemoryCacheBackend()


# Backwards compatibility with the previous placeholder API.
def get_redis_url(settings: Settings) -> str | None:
    return settings.redis_url
